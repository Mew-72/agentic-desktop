from google.adk.agents import Agent
from google.adk.tools import McpToolset, MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types
from google.adk.planners import BuiltInPlanner

# playwright_mcp = McpToolset(
#     connection_params=StdioConnectionParams(
#         server_params=StdioServerParameters(
#             command="npx.cmd",
#             args=["-y", "@playwright/mcp@latest"],
#         )
#     )
# )

# playwright_mcp = McpToolset(
#     connection_params=StdioConnectionParams(
#         server_params=StdioServerParameters(
#             command='npx',
#             args=['-y', '@modelcontextprotocol/server-puppeteer']
#         )
#     )
# )

playwright_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@playwright/mcp@latest"],
        ),
        timeout=15
    )
)

browser_assistant = Agent(
    model="gemini-2.5-pro",
    # model="gemini-2.5-flash-lite",
    name="browser_assistant",
    description="A specialist in automating browsers and web testing via Playwright.",
    instruction=(
        "You are the Browser specialist agent. You can automate web browsers, "
        "interact with sites, scrape information, and run tests using Playwright. "
        "When your task is complete or you need to hand off to another agent, "
        "use the transfer_to_agent tool."
    ),
    tools=[playwright_mcp],
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            thinking_budget=512,
            include_thoughts=True
            ),
    ),
)
