"""Dedicated websocket server for bidirectional, session-aware realtime communication."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable

import websockets
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger(__name__)


class EventType(StrEnum):
    """Protocol event names shared by clients and server."""

    SESSION_CONNECTED = "session.connected"
    SESSION_HEARTBEAT = "session.heartbeat"
    SESSION_DISCONNECT = "session.disconnect"
    SESSION_CLEANUP = "session.cleanup"

    AUDIO_CHUNK_IN = "audio.chunk.in"
    AUDIO_CHUNK_OUT = "audio.chunk.out"
    TEXT_INPUT = "text.input"
    TEXT_OUTPUT_DELTA = "text.output.delta"
    TRANSCRIPT_DELTA = "transcript.delta"

    STATUS_UPDATE = "status.update"
    CANCEL = "cancel"
    ERROR = "error"


@dataclass(slots=True)
class Event:
    """Generic event envelope for transport-agnostic payloads."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_json(self) -> str:
        body: dict[str, Any] = {
            "type": self.type,
            "payload": self.payload,
            "timestamp_ms": self.timestamp_ms,
        }
        if self.request_id is not None:
            body["request_id"] = self.request_id
        return json.dumps(body)

    @classmethod
    def from_json(cls, raw: str) -> "Event":
        parsed = json.loads(raw)
        return cls(
            type=parsed["type"],
            payload=parsed.get("payload", {}),
            request_id=parsed.get("request_id"),
            timestamp_ms=parsed.get("timestamp_ms", int(time.time() * 1000)),
        )


@dataclass(slots=True)
class Session:
    """Single websocket client session state."""

    session_id: str
    websocket: WebSocketServerProtocol
    created_at: float = field(default_factory=time.monotonic)
    last_heartbeat: float = field(default_factory=time.monotonic)
    generation_task: asyncio.Task[None] | None = None
    closing: bool = False


EventHandler = Callable[[Session, Event], Awaitable[list[Event]]]


class RealtimeWebSocketServer:
    """Websocket server with per-session lifecycle, heartbeats, and interruption support."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        heartbeat_timeout_s: float = 30.0,
        event_handler: EventHandler | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self._event_handler = event_handler or self._default_event_handler
        self._sessions: dict[str, Session] = {}
        self._sessions_lock = asyncio.Lock()

    async def start(self) -> None:
        async with websockets.serve(self._handle_connection, self.host, self.port):
            logger.info("Realtime websocket server listening on ws://%s:%s", self.host, self.port)
            await asyncio.Future()

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        session = Session(session_id=str(uuid.uuid4()), websocket=websocket)
        await self._register_session(session)

        heartbeat_task = asyncio.create_task(self._heartbeat_monitor(session))
        try:
            await self._send_event(
                session,
                Event(
                    type=EventType.SESSION_CONNECTED,
                    payload={"session_id": session.session_id},
                ),
            )

            async for raw_message in websocket:
                await self._handle_incoming_message(session, raw_message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected for session %s", session.session_id)
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(Exception):
                await heartbeat_task
            await self._cleanup_session(session, reason="socket_closed")

    async def _handle_incoming_message(self, session: Session, raw_message: str) -> None:
        try:
            event = Event.from_json(raw_message)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            await self._send_error(session, f"Invalid event payload: {exc}")
            return

        if event.type == EventType.SESSION_HEARTBEAT:
            session.last_heartbeat = time.monotonic()
            await self._send_event(
                session,
                Event(type=EventType.STATUS_UPDATE, payload={"state": "heartbeat_ack"}),
            )
            return

        if event.type in (EventType.CANCEL, EventType.SESSION_DISCONNECT):
            await self._cancel_generation(session)
            if event.type == EventType.SESSION_DISCONNECT:
                await self._cleanup_session(session, reason="client_disconnect")
            return

        await self._start_generation(session, event)

    async def _start_generation(self, session: Session, event: Event) -> None:
        if session.generation_task and not session.generation_task.done():
            await self._cancel_generation(session)

        session.generation_task = asyncio.create_task(self._run_event_handler(session, event))

    async def _run_event_handler(self, session: Session, event: Event) -> None:
        try:
            await self._send_event(
                session,
                Event(type=EventType.STATUS_UPDATE, payload={"state": "processing", "input_type": event.type}),
            )
            outbound_events = await self._event_handler(session, event)
            for outbound in outbound_events:
                await self._send_event(session, outbound)
            await self._send_event(session, Event(type=EventType.STATUS_UPDATE, payload={"state": "idle"}))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive boundary for custom handlers
            logger.exception("Error in event handler for session %s", session.session_id)
            await self._send_error(session, f"Event handling failed: {exc}")

    async def _cancel_generation(self, session: Session) -> None:
        task = session.generation_task
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await self._send_event(
                session,
                Event(type=EventType.STATUS_UPDATE, payload={"state": "interrupted"}),
            )

    async def _heartbeat_monitor(self, session: Session) -> None:
        try:
            while True:
                await asyncio.sleep(max(1.0, self.heartbeat_timeout_s / 3))
                elapsed = time.monotonic() - session.last_heartbeat
                if elapsed <= self.heartbeat_timeout_s:
                    continue
                await self._send_error(
                    session,
                    f"Heartbeat timed out after {self.heartbeat_timeout_s:.1f}s",
                )
                await self._cleanup_session(session, reason="heartbeat_timeout")
                return
        except asyncio.CancelledError:
            return

    async def _register_session(self, session: Session) -> None:
        async with self._sessions_lock:
            self._sessions[session.session_id] = session

    async def _cleanup_session(self, session: Session, reason: str) -> None:
        if session.closing:
            return

        session.closing = True
        await self._cancel_generation(session)

        async with self._sessions_lock:
            self._sessions.pop(session.session_id, None)

        await self._safe_send(
            session,
            Event(
                type=EventType.SESSION_CLEANUP,
                payload={"session_id": session.session_id, "reason": reason},
            ),
        )

        if not session.websocket.closed:
            with contextlib.suppress(Exception):
                await session.websocket.close()

    async def _send_error(self, session: Session, message: str) -> None:
        await self._safe_send(session, Event(type=EventType.ERROR, payload={"message": message}))

    async def _send_event(self, session: Session, event: Event) -> None:
        await self._safe_send(session, event)

    async def _safe_send(self, session: Session, event: Event) -> None:
        if session.websocket.closed:
            return

        try:
            await session.websocket.send(event.to_json())
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed while sending event for session %s", session.session_id)

    @staticmethod
    async def _default_event_handler(session: Session, event: Event) -> list[Event]:
        """Simple generic fallback behavior for text/audio streaming events."""
        if event.type == EventType.TEXT_INPUT:
            user_text = str(event.payload.get("text", ""))
            return [
                Event(type=EventType.TRANSCRIPT_DELTA, payload={"role": "user", "delta": user_text}),
                Event(type=EventType.TEXT_OUTPUT_DELTA, payload={"delta": f"Echo: {user_text}"}),
            ]

        if event.type == EventType.AUDIO_CHUNK_IN:
            audio_chunk = event.payload.get("chunk")
            return [
                Event(type=EventType.TRANSCRIPT_DELTA, payload={"role": "user", "delta": "[audio chunk received]"}),
                Event(type=EventType.AUDIO_CHUNK_OUT, payload={"chunk": audio_chunk}),
            ]

        return [
            Event(
                type=EventType.STATUS_UPDATE,
                payload={"state": "ignored", "event_type": event.type},
            )
        ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(RealtimeWebSocketServer().start())
