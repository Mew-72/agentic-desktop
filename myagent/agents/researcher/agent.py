from google.adk.agents import Agent
from ...tools import execute_command
from google.genai import types

researcher_assistant = Agent(
    model="gemini-2.5-flash",
    name="researcher_assistant",
    description="A specialist in general research, web search, and answering questions.",
    instruction=(
        "You are the Researcher specialist agent. Your goal is to find answers "
        "and provide clear explanations to the user's questions. "
        "When your task is complete or you need to hand off to another agent, "
        "use the transfer_to_agent tool."
    ),
    tools=[],
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=1024)
    ),
)
