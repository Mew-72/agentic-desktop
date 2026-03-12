from google.adk.agents import Agent
from google.adk.tools import transfer_to_agent

from .prompt import ROUTER_INSTRUCTION
from .agents import (
    terminal_assistant,
    github_assistant,
    coder_assistant,
    researcher_assistant,
)

root_agent = Agent(
    # model="gemini-2.5-flash",
    model="gemini-2.5-flash-native-audio-latest",
    name="jarvis",
    description="Main entry point. A general-purpose AI assistant that routes users to specialists.",
    instruction=ROUTER_INSTRUCTION,
    # sub_agents=[
    #     terminal_assistant,
    #     github_assistant,
    #     coder_assistant,
    #     researcher_assistant,
    # ],
)
