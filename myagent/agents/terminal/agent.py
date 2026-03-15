from google.adk.agents import Agent

from .prompt import SYSTEM_INSTRUCTION
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
import sys
import os

server_script = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "servers", "shell-mcp", "server.py")
)

shell_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[server_script],
        ),
        timeout=30
    )
)

terminal_assistant = Agent(
    # model="gemini-2.5-flash",
    model="gemini-2.5-flash-lite",
    name="terminal_assistant",
    description=(
        "A terminal specialist that translates natural language "
        "into shell commands, executes them safely, explains errors, and "
        "manages reusable workflows using the Shell MCP Server."
    ),
    instruction=SYSTEM_INSTRUCTION + "\n\nWhen your task is complete or you need to hand off to another agent, use the transfer_to_agent tool.",
    tools=[shell_mcp],
)
