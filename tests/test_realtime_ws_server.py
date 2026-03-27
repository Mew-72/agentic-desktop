import asyncio
import json
import unittest

from myagent.servers.realtime_ws_server import Event, EventType, RealtimeWebSocketServer, Session


class FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []
        self.closed = False

    async def send(self, payload: str):
        self.sent.append(payload)

    async def close(self):
        self.closed = True


class RealtimeServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_and_audio_events_emit_bidirectional_payloads(self):
        server = RealtimeWebSocketServer()
        ws = FakeWebSocket()
        session = Session(session_id="s1", websocket=ws)

        await server._handle_incoming_message(
            session,
            Event(type=EventType.TEXT_INPUT, payload={"text": "hello"}).to_json(),
        )
        await asyncio.sleep(0)

        await server._handle_incoming_message(
            session,
            Event(type=EventType.AUDIO_CHUNK_IN, payload={"chunk": "base64-audio"}).to_json(),
        )
        await asyncio.sleep(0)

        sent_types = [json.loads(m)["type"] for m in ws.sent]
        self.assertIn(EventType.TEXT_OUTPUT_DELTA, sent_types)
        self.assertIn(EventType.AUDIO_CHUNK_OUT, sent_types)

    async def test_cancel_interrupts_inflight_generation(self):
        async def slow_handler(_session: Session, _event: Event):
            await asyncio.sleep(10)
            return []

        server = RealtimeWebSocketServer(event_handler=slow_handler)
        ws = FakeWebSocket()
        session = Session(session_id="s2", websocket=ws)

        await server._handle_incoming_message(
            session,
            Event(type=EventType.TEXT_INPUT, payload={"text": "long task"}).to_json(),
        )
        await asyncio.sleep(0)

        await server._handle_incoming_message(session, Event(type=EventType.CANCEL).to_json())

        sent = [json.loads(m) for m in ws.sent]
        interrupted = [m for m in sent if m["type"] == EventType.STATUS_UPDATE and m["payload"].get("state") == "interrupted"]
        self.assertTrue(interrupted)

    async def test_cleanup_removes_session_and_closes_socket(self):
        server = RealtimeWebSocketServer()
        ws = FakeWebSocket()
        session = Session(session_id="s3", websocket=ws)

        await server._register_session(session)
        self.assertIn("s3", server._sessions)

        await server._cleanup_session(session, reason="unit_test")

        self.assertNotIn("s3", server._sessions)
        self.assertTrue(ws.closed)
        cleanup_events = [json.loads(m) for m in ws.sent if json.loads(m)["type"] == EventType.SESSION_CLEANUP]
        self.assertEqual(cleanup_events[0]["payload"]["reason"], "unit_test")

    async def test_multiple_sessions_can_process_concurrently(self):
        server = RealtimeWebSocketServer()
        ws1 = FakeWebSocket()
        ws2 = FakeWebSocket()
        s1 = Session(session_id="a", websocket=ws1)
        s2 = Session(session_id="b", websocket=ws2)

        await asyncio.gather(server._register_session(s1), server._register_session(s2))

        await asyncio.gather(
            server._handle_incoming_message(s1, Event(type=EventType.TEXT_INPUT, payload={"text": "one"}).to_json()),
            server._handle_incoming_message(s2, Event(type=EventType.TEXT_INPUT, payload={"text": "two"}).to_json()),
        )
        await asyncio.sleep(0)

        sent1 = [json.loads(m) for m in ws1.sent]
        sent2 = [json.loads(m) for m in ws2.sent]
        self.assertTrue(any(m["type"] == EventType.TEXT_OUTPUT_DELTA for m in sent1))
        self.assertTrue(any(m["type"] == EventType.TEXT_OUTPUT_DELTA for m in sent2))


if __name__ == "__main__":
    unittest.main()
