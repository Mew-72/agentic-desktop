from google.adk.agents import Agent
from ...tools import execute_command

researcher_assistant = Agent(
    model="gemini-2.5-pro",
    name="researcher_assistant",
    description="A specialist in general research, web search, and answering questions.",
    instruction=(
        "You are the Researcher specialist agent. Your goal is to find answers "
        "and provide clear explanations to the user's questions. You can use "
        "the tools available to you to gather information if needed. "
        "When your task is complete or you need to hand off to another agent, "
        "use the transfer_to_agent tool."
    ),
    tools=[],  # We can add a google_search tool later if available
)
