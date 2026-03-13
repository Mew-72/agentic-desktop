from google.adk.agents import Agent
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types
from google.adk.planners import BuiltInPlanner
import sys
import os

server_script = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "servers", "file-management-mcp", "server.py")
)

file_manager_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[server_script],
        ),
        timeout=15
    )
)

file_manager_assistant = Agent(
    model="gemini-2.5-flash",
    name="file_manager_assistant",
    description="A specialist in secure file management operations.",
    instruction=(
        "You are the Secure File Management specialist agent. You can automate file operations, "
        "read/write/search files, and manage directories. "
        "All file operations are strictly restricted to pre-approved directories. "
        "When your task is complete or you need to hand off to another agent, "
        "use the transfer_to_agent tool."
    ),
    tools=[file_manager_mcp],
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            thinking_budget=1024,
            include_thoughts=True
            ),
    ),
)
