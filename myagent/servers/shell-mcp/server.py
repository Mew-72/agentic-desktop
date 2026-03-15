"""
Shell MCP Server
================

An MCP server that safely executes shell commands (including ls, grep, etc.)
and manages reusable workflows. It replaces the built-in python tools previously 
used by the terminal agent.
"""

import os
import json
import platform
import subprocess
import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# ──────────────────────────────────────────────
# Initialize
# ──────────────────────────────────────────────

mcp = FastMCP(
    "Shell Server",
    instructions=(
        "This server provides shell execution capabilities and workflow management. "
        "It runs commands in the native system shell. On Windows, it uses PowerShell "
        "by default, but can use git bash or WSL if explicitly requested in the command."
    ),
)

# In-memory storage for workflows and command history
# In a production app, workflows could be saved to a local sqlite DB or JSON file.
_WORKFLOWS_FILE = Path(__file__).parent / "workflows.json"
command_history = []


def _load_workflows() -> dict:
    if _WORKFLOWS_FILE.exists():
        try:
            with open(_WORKFLOWS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_workflows(workflows: dict) -> None:
    _WORKFLOWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_WORKFLOWS_FILE, "w", encoding="utf-8") as f:
        json.dump(workflows, f, indent=2)


# Dangerous command patterns that should be blocked
BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/\s*$",         # rm -rf /
    r"rm\s+-rf\s+/\*",           # rm -rf /*
    r"rm\s+-rf\s+~",             # rm -rf ~
    r"mkfs\.",                    # mkfs.ext4 etc.
    r"dd\s+if=.*of=/dev/",       # dd overwrite disk
    r":\(\)\s*\{\s*:\|:\&\s*\};:",  # fork bomb
    r"format\s+[a-zA-Z]:",       # Windows format drive
    r"del\s+/s\s+/q\s+[cC]:\\",  # Windows recursive delete C:\
    r"Remove-Item\s+-Recurse.*[cC]:\\$",  # PowerShell recursive delete C:\
    r"shutdown\s",               # shutdown commands
    r"reboot\s*$",               # reboot
    r"init\s+0",                 # init 0
    r"chmod\s+-R\s+777\s+/\s*$", # chmod 777 /
]


def _is_command_blocked(command: str) -> bool:
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command.strip(), re.IGNORECASE):
            return True
    return False


def _get_shell_config():
    if platform.system() == "Windows":
        return {"shell": True, "executable": "powershell.exe"}
    else:
        return {"shell": True, "executable": "/bin/bash"}


# ──────────────────────────────────────────────
# Tool 1: Execute Command
# ──────────────────────────────────────────────

@mcp.tool()
def execute_command(command: str, working_directory: str = ".", dry_run: bool = False) -> str:
    """
    Execute a shell command on the local machine.

    Args:
        command: The shell command to execute (e.g., 'ls -la', 'grep foo bar.txt').
        working_directory: Directory to run the command in. Defaults to current directory.
        dry_run: If True, return the command without executing it.

    Returns:
        JSON string containing the command, stdout, stderr, exit_code, and working_directory.
    """
    if _is_command_blocked(command):
        return json.dumps({
            "command": command,
            "stdout": "",
            "stderr": f"BLOCKED: This command matches a dangerous pattern and was refused for safety. Command: {command}",
            "exit_code": -1,
            "working_directory": working_directory,
            "blocked": True,
        }, indent=2)

    if dry_run:
        return json.dumps({
            "command": command,
            "stdout": "[DRY RUN] Command was not executed.",
            "stderr": "",
            "exit_code": 0,
            "working_directory": working_directory,
            "dry_run": True,
        }, indent=2)

    shell_config = _get_shell_config()
    try:
        # Resolve working directory
        cwd = Path(working_directory).resolve()
        
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=60,
            **shell_config,
        )
        result = {
            "command": command,
            "stdout": proc.stdout[:5000] if proc.stdout else "",
            "stderr": proc.stderr[:2000] if proc.stderr else "",
            "exit_code": proc.returncode,
            "working_directory": str(cwd),
        }
    except subprocess.TimeoutExpired:
        result = {
            "command": command,
            "stdout": "",
            "stderr": "ERROR: Command timed out after 60 seconds.",
            "exit_code": -1,
            "working_directory": working_directory,
        }
    except FileNotFoundError:
        result = {
            "command": command,
            "stdout": "",
            "stderr": f"ERROR: Working directory not found: {working_directory}",
            "exit_code": -1,
            "working_directory": working_directory,
        }
    except Exception as e:
        result = {
            "command": command,
            "stdout": "",
            "stderr": f"ERROR: {type(e).__name__}: {str(e)}",
            "exit_code": -1,
            "working_directory": working_directory,
        }

    command_history.append(result)
    return json.dumps(result, indent=2)


# ──────────────────────────────────────────────
# Tool 2: Explain Error
# ──────────────────────────────────────────────

@mcp.tool()
def explain_error(command: str, stdout: str, stderr: str, exit_code: int) -> str:
    """
    Package error details from a failed command for analysis.

    Args:
        command: The command that failed.
        stdout: The standard output from the failed command.
        stderr: The standard error from the failed command.
        exit_code: The numeric exit code of the failed command.

    Returns:
        A formatted string with error details requesting an explanation.
    """
    result = {
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "analysis_request": (
            "Please analyze this command failure. Explain what went wrong in "
            "simple, beginner-friendly language, and suggest a corrected command "
            "or an alternative approach."
        ),
    }
    return json.dumps(result, indent=2)


# ──────────────────────────────────────────────
# Tool 3: Save Workflow
# ──────────────────────────────────────────────

@mcp.tool()
def save_workflow(name: str, description: str, commands: list[str], parameters: str = "") -> str:
    """
    Save a sequence of commands as a reusable named workflow.

    Args:
        name: A short, descriptive name for the workflow.
        description: A brief description of what the workflow does.
        commands: Ordered list of shell commands in the workflow. Uses <param> syntax.
        parameters: Comma-separated list of parameter names used in the commands.

    Returns:
        Confirmation message.
    """
    param_list = [p.strip() for p in parameters.split(",") if p.strip()] if parameters else []
    
    workflow = {
        "name": name,
        "description": description,
        "commands": commands,
        "parameters": param_list,
    }

    workflows = _load_workflows()
    workflows[name] = workflow
    _save_workflows(workflows)

    param_info = f" (parameters: {', '.join(param_list)})" if param_list else ""
    return (
        f"Workflow '{name}' saved successfully with {len(commands)} commands{param_info}.\n"
        f"Description: {description}\n"
        f"Commands:\n" + "\n".join(f"  {i+1}. {cmd}" for i, cmd in enumerate(commands))
    )


# ──────────────────────────────────────────────
# Tool 4: List Workflows
# ──────────────────────────────────────────────

@mcp.tool()
def list_workflows() -> str:
    """
    List all saved workflows.

    Returns:
        JSON representation of all saved workflows.
    """
    workflows = _load_workflows()

    if not workflows:
        return json.dumps({"message": "No workflows saved yet.", "workflows": {}}, indent=2)

    summary = {}
    for name, wf in workflows.items():
        summary[name] = {
            "description": wf["description"],
            "commands": wf["commands"],
            "parameters": wf["parameters"],
        }

    return json.dumps({"message": f"Found {len(summary)} saved workflow(s).", "workflows": summary}, indent=2)


# ──────────────────────────────────────────────
# Tool 5: Run Workflow
# ──────────────────────────────────────────────

@mcp.tool()
def run_workflow(name: str, parameter_values: str = "") -> str:
    """
    Retrieve a saved workflow and prepare its commands for execution.

    Args:
        name: The name of the workflow to run.
        parameter_values: A JSON string mapping parameter names to their values.

    Returns:
        JSON string containing the resolved commands ready for execution.
    """
    parsed_params = {}
    if parameter_values:
        try:
            parsed_params = json.loads(parameter_values)
        except json.JSONDecodeError:
            return json.dumps({"error": f"Invalid JSON for parameter_values: {parameter_values}"}, indent=2)

    workflows = _load_workflows()

    if name not in workflows:
        available = list(workflows.keys()) if workflows else []
        return json.dumps({
            "error": f"Workflow '{name}' not found.",
            "available_workflows": available,
        }, indent=2)

    workflow = workflows[name]

    # Substitute parameters in commands
    resolved_commands = []
    for cmd in workflow["commands"]:
        resolved = cmd
        for param_name, param_value in parsed_params.items():
            resolved = resolved.replace(f"{{{param_name}}}", str(param_value))
            # Also support <param> syntax replacing
            resolved = resolved.replace(f"<{param_name}>", str(param_value))
        resolved_commands.append(resolved)

    missing_params = set()
    for cmd in resolved_commands:
        matches = re.findall(r"\{(\w+)\}", cmd) + re.findall(r"<(\w+)>", cmd)
        missing_params.update(matches)

    if missing_params:
        return json.dumps({
            "error": f"Missing parameter values for: {', '.join(missing_params)}",
            "workflow": workflow,
            "required_parameters": list(missing_params),
        }, indent=2)

    return json.dumps({
        "workflow_name": name,
        "description": workflow["description"],
        "commands_to_execute": resolved_commands,
        "instruction": (
            "Execute these commands one by one using the execute_command tool. "
            "Ask the user for confirmation before each command."
        ),
    }, indent=2)


if __name__ == "__main__":
    import sys as _sys
    print("🚀 Starting Shell MCP Server...", file=_sys.stderr)
    mcp.run(transport="stdio")
