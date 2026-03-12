"""Shell command execution tool for the terminal assistant agent."""

import subprocess
import platform
import re
from google.adk.tools import ToolContext


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
    """Check if a command matches any blocked dangerous pattern."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command.strip(), re.IGNORECASE):
            return True
    return False


def _get_shell_config():
    """Return the appropriate shell command prefix for the current OS."""
    if platform.system() == "Windows":
        return {"shell": True, "executable": "powershell.exe"}
    else:
        return {"shell": True, "executable": "/bin/bash"}


def execute_command(
    command: str,
    working_directory: str = ".",
    dry_run: bool = False,
    tool_context: ToolContext = None,
) -> dict:
    """Execute a shell command on the local machine.

    This tool runs a shell command and returns the output. It includes safety
    checks to block dangerous commands. Use dry_run=True to preview the command
    without executing it.

    Args:
        command: The shell command to execute.
        working_directory: Directory to run the command in. Defaults to current directory.
        dry_run: If True, return the command without executing it. Defaults to False.

    Returns:
        A dictionary containing the command, stdout, stderr, exit_code,
        and working_directory.
    """
    # Safety check
    if _is_command_blocked(command):
        result = {
            "command": command,
            "stdout": "",
            "stderr": f"BLOCKED: This command matches a dangerous pattern and was refused for safety. Command: {command}",
            "exit_code": -1,
            "working_directory": working_directory,
            "blocked": True,
        }
        return result

    # Dry run mode
    if dry_run:
        result = {
            "command": command,
            "stdout": "[DRY RUN] Command was not executed.",
            "stderr": "",
            "exit_code": 0,
            "working_directory": working_directory,
            "dry_run": True,
        }
        return result

    # Execute the command
    shell_config = _get_shell_config()
    try:
        proc = subprocess.run(
            command,
            cwd=working_directory,
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
            "working_directory": working_directory,
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

    # Store in session state for history
    if tool_context:
        history = tool_context.state.get("command_history", [])
        history = history + [result]
        tool_context.state["command_history"] = history

    return result


def explain_error(
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int,
) -> dict:
    """Package error details from a failed command for the agent to analyze.

    Call this tool when a previously executed command has failed (non-zero exit
    code). It structures the error information so the agent can provide a
    human-friendly explanation and suggest a fix.

    Args:
        command: The command that failed.
        stdout: The standard output from the failed command.
        stderr: The standard error from the failed command.
        exit_code: The numeric exit code of the failed command.

    Returns:
        A structured dictionary with all error context and a request for analysis.
    """
    return {
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
