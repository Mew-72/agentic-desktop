from google.adk.agents import Agent
from google.genai import types
from ...tools import execute_command, explain_error

coder_assistant = Agent(
    model="gemini-2.5-flash",
    name="coder_assistant",
    description="A specialist in writing, reading, and refactoring local code files.",
    instruction=(
        "You are the Coding specialist agent, built to read, write, and refactor "
        "code in the user's local workspace. You can use the execute_command tool "
        "to run tools like grep, cat, or sed if needed, or to run tests and scripts. "
        "Always be clear about what files you are modifying. "
        "When your task is complete or you need to hand off to another agent, "
        "use the transfer_to_agent tool."
    ),
    tools=[execute_command, explain_error],
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=1024)
    ),
)
