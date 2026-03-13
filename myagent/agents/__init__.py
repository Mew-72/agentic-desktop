from .terminal.agent import terminal_assistant
from .github.agent import github_assistant
from .coder.agent import coder_assistant
from .researcher.agent import researcher_assistant
from .browser.agent import browser_assistant
from .file_manager.agent import file_manager_assistant

__all__ = [
    "terminal_assistant",
    "github_assistant",
    "coder_assistant",
    "researcher_assistant",
    "browser_assistant",
    "file_manager_assistant",
]
