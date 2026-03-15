from google.adk.agents import Agent
from google.adk.tools import transfer_to_agent
from google.adk.tools import google_search, AgentTool
from google.adk.planners import BuiltInPlanner
from google.genai import types
from google.adk.models.google_llm import Gemini

from .prompt import ROUTER_INSTRUCTION
from .agents import (
    terminal_assistant,
    github_assistant,
    coder_assistant,
    researcher_assistant,
    browser_assistant,
    file_manager_assistant,
)

root_agent = Agent(
    model=Gemini(model="gemini-2.5-flash-lite"),
    # model="gemini-2.5-flash-native-audio-latest",
    name="jarvis",
    description="Main entry point. A general-purpose AI assistant that routes users to specialists.",
    instruction=ROUTER_INSTRUCTION,
    sub_agents=[
        terminal_assistant,
        github_assistant,
        coder_assistant,
        researcher_assistant,
        browser_assistant,
        file_manager_assistant,
    ],
    # tools=[AgentTool(searching_agent)],
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            thinking_budget=1024,
            include_thoughts=True
            ),
    ),
)
