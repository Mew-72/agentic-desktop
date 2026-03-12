"""Workflow management tools for saving and replaying command sequences."""

from google.adk.tools import ToolContext


def save_workflow(
    name: str,
    description: str,
    commands: list[str],
    parameters: str = "",
    tool_context: ToolContext = None,
) -> str:
    """Save a sequence of commands as a reusable named workflow.

    Use this tool after the user has run a successful sequence of commands
    and wants to save them for later reuse. Parameters are placeholders
    that can be substituted when the workflow is run later.

    Args:
        name: A short, descriptive name for the workflow (e.g. "build_and_test").
        description: A brief description of what the workflow does.
        commands: Ordered list of shell commands in the workflow.
            Use angle-bracket syntax for parameters, e.g. "cd <project_path>".
        parameters: Comma-separated list of parameter names used in the commands
            (e.g. "project_path,branch_name"). Leave empty if no parameters.

    Returns:
        Confirmation message with the saved workflow details.
    """
    param_list = [p.strip() for p in parameters.split(",") if p.strip()] if parameters else []

    workflow = {
        "name": name,
        "description": description,
        "commands": commands,
        "parameters": param_list,
    }

    if tool_context:
        workflows = tool_context.state.get("workflows", {})
        workflows = {**workflows, name: workflow}
        tool_context.state["workflows"] = workflows

    param_info = f" (parameters: {', '.join(param_list)})" if param_list else ""
    return (
        f"Workflow '{name}' saved successfully with {len(commands)} commands{param_info}.\n"
        f"Description: {description}\n"
        f"Commands:\n" + "\n".join(f"  {i+1}. {cmd}" for i, cmd in enumerate(commands))
    )


def list_workflows(
    tool_context: ToolContext = None,
) -> dict:
    """List all saved workflows in the current session.

    Returns:
        A dictionary mapping workflow names to their details
        (description, commands, parameters).
    """
    if tool_context:
        workflows = tool_context.state.get("workflows", {})
    else:
        workflows = {}

    if not workflows:
        return {"message": "No workflows saved yet.", "workflows": {}}

    summary = {}
    for name, wf in workflows.items():
        summary[name] = {
            "description": wf["description"],
            "commands": wf["commands"],
            "parameters": wf["parameters"],
        }

    return {"message": f"Found {len(summary)} saved workflow(s).", "workflows": summary}


def run_workflow(
    name: str,
    parameter_values: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Retrieve a saved workflow and prepare its commands for execution.

    This tool fetches a workflow by name, substitutes any parameters with
    the provided values, and returns the ready-to-execute commands.
    You should then execute each returned command one by one using the
    execute_command tool, asking the user for confirmation before each.

    Args:
        name: The name of the workflow to run.
        parameter_values: A JSON string mapping parameter names to their values
            for this run, e.g. '{"project_path": "/home/user/myproject"}'.
            Leave empty if the workflow has no parameters.

    Returns:
        A dictionary with the workflow details and the resolved commands
        ready for execution.
    """
    import json

    parsed_params = {}
    if parameter_values:
        try:
            parsed_params = json.loads(parameter_values)
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON for parameter_values: {parameter_values}"}

    if tool_context:
        workflows = tool_context.state.get("workflows", {})
    else:
        workflows = {}

    if name not in workflows:
        available = list(workflows.keys()) if workflows else []
        return {
            "error": f"Workflow '{name}' not found.",
            "available_workflows": available,
        }

    workflow = workflows[name]

    # Substitute parameters in commands
    resolved_commands = []
    for cmd in workflow["commands"]:
        resolved = cmd
        for param_name, param_value in parsed_params.items():
            resolved = resolved.replace(f"{{{param_name}}}", str(param_value))
        resolved_commands.append(resolved)

    # Check for unresolved placeholders
    import re
    missing_params = set()
    for cmd in resolved_commands:
        matches = re.findall(r"\{(\w+)\}", cmd)
        missing_params.update(matches)

    if missing_params:
        return {
            "error": f"Missing parameter values for: {', '.join(missing_params)}",
            "workflow": workflow,
            "required_parameters": list(missing_params),
        }

    return {
        "workflow_name": name,
        "description": workflow["description"],
        "commands_to_execute": resolved_commands,
        "instruction": (
            "Execute these commands one by one using the execute_command tool. "
            "Ask the user for confirmation before each command."
        ),
    }
