import os
from google.adk.agents import Agent
from google.adk.tools import McpToolset
from mcp import StdioServerParameters

github_tools = McpToolset(
    connection_params=StdioServerParameters(
        command="docker",
        args=[
            "run",
            "-i",
            "--rm",
            "-e",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            "-e",
            "GITHUB_HOST",
            "ghcr.io/github/github-mcp-server",
        ],
        env={
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", ""),
            "GITHUB_HOST": "https://github.com",
        },
    )
)

github_assistant = Agent(
    model="gemini-2.5-flash",
    name="github_assistant",
    description="A specialist in GitHub operations: repos, issues, PRs.",
    instruction=(
        "You are the GitHub specialist agent. You can read, search, and modify "
        "GitHub repositories, issues, and pull requests using your MCP tools. "
        "When your task is complete or you need to hand off to another agent, "
        "use the transfer_to_agent tool. Keep your answers concise and action-oriented."
    ),
    tools=[github_tools],
)
