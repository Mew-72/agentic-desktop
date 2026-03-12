from google.adk.agents import Agent

from .prompt import SYSTEM_INSTRUCTION
from ...tools import (
    execute_command,
    explain_error,
    save_workflow,
    list_workflows,
    run_workflow,
)

terminal_assistant = Agent(
    model="gemini-2.5-flash",
    name="terminal_assistant",
    description=(
        "A terminal specialist that translates natural language "
        "into shell commands, executes them safely, explains errors, and "
        "manages reusable workflows."
    ),
    instruction=SYSTEM_INSTRUCTION + "\n\nWhen your task is complete or you need to hand off to another agent, use the transfer_to_agent tool.",
    tools=[
        execute_command,
        explain_error,
        save_workflow,
        list_workflows,
        run_workflow,
    ],
)
