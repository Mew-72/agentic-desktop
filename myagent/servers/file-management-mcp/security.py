"""
Security module for the File Management MCP Server.

This module handles:
- Allowed directories whitelist management
- Path validation and sanitization
- Directory traversal attack prevention
- Protected file detection (important files need user approval)
- Operation logging for audit trails
"""

import os
import sys
import json
import logging
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import Optional

# Configure logging — MUST go to stderr, not stdout
# MCP stdio transport uses stdout for JSON-RPC communication
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logger = logging.getLogger("file-mcp-security")
logger.addHandler(_handler)
logger.setLevel(logging.INFO)


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


class ApprovalRequired(Exception):
    """Raised when user approval is needed for a sensitive operation."""
    pass


class PathValidator:
    """
    Validates file paths against an allowed directories whitelist.
    Also detects protected/important files that require user approval.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.allowed_directories: list[Path] = []
        self.max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB default
        self.log_operations: bool = True
        self.confirm_pin: str = "1234"  # Default PIN, change in config.json

        # Protected file settings
        self.protected_extensions: list[str] = [
            ".env", ".key", ".pem", ".crt", ".pfx",
            ".db", ".sqlite", ".sql",
            ".exe", ".dll", ".sys",
            ".bat", ".cmd", ".ps1",
            ".conf", ".cfg", ".ini",
        ]
        self.protected_patterns: list[str] = [
            "password*", "secret*", "credential*",
            "*.backup", "*.bak",
            ".git*", ".ssh*",
        ]
        self.always_confirm_operations: list[str] = [
            "delete_file",
            "rename_file",
            "write_file_overwrite",
        ]

        self._load_config(config_path)

    def _load_config(self, config_path: Optional[str] = None) -> None:
        """Load config from environment variable or config file."""

        # Priority 1: Environment variable for directories
        env_dirs = os.environ.get("ALLOWED_DIRECTORIES", "")
        if env_dirs:
            dirs = [d.strip() for d in env_dirs.split(",") if d.strip()]
            self.allowed_directories = [Path(d).resolve() for d in dirs]
            logger.info(
                f"Loaded {len(self.allowed_directories)} allowed directories from environment"
            )

        # Load config file for ALL settings (including protected files)
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config.json",
            )

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)

                # Only load dirs from config if not already set from env
                if not self.allowed_directories:
                    dirs = config.get("allowed_directories", [])
                    self.allowed_directories = [Path(d).resolve() for d in dirs]

                self.max_file_size_bytes = (
                    config.get("max_file_size_mb", 10) * 1024 * 1024
                )
                self.log_operations = config.get("log_operations", True)

                # Protected file settings
                if "protected_extensions" in config:
                    self.protected_extensions = config["protected_extensions"]
                if "protected_patterns" in config:
                    self.protected_patterns = config["protected_patterns"]
                if "always_confirm_operations" in config:
                    self.always_confirm_operations = config["always_confirm_operations"]
                if "confirm_pin" in config:
                    self.confirm_pin = str(config["confirm_pin"])

                logger.info(
                    f"Config loaded: {len(self.allowed_directories)} allowed dirs, "
                    f"{len(self.protected_extensions)} protected extensions"
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to load config: {e}")
                raise SecurityError(f"Invalid config file: {e}")
        elif not self.allowed_directories:
            logger.warning(
                "No config found. No directories are allowed. "
                "Set ALLOWED_DIRECTORIES env var or create config.json"
            )

    def validate_path(self, path: str, must_exist: bool = False) -> Path:
        """
        Validate a path against the allowed directories whitelist.

        Raises:
            SecurityError: If the path is outside allowed directories
            FileNotFoundError: If must_exist=True and path doesn't exist
        """
        if not self.allowed_directories:
            raise SecurityError(
                "No allowed directories configured. "
                "Set ALLOWED_DIRECTORIES env var or update config.json"
            )

        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError) as e:
            raise SecurityError(f"Invalid path: {e}")

        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"Path does not exist: {resolved}")

        is_allowed = any(
            self._is_subpath(resolved, allowed_dir)
            for allowed_dir in self.allowed_directories
        )

        if not is_allowed:
            if self.log_operations:
                logger.warning(
                    f"🚫 ACCESS DENIED: '{path}' → '{resolved}' outside allowed dirs"
                )
            raise SecurityError(
                f"Access denied: '{path}' is outside allowed directories.\n"
                f"Allowed directories: {[str(d) for d in self.allowed_directories]}"
            )

        if self.log_operations:
            logger.info(f"✅ Access granted: '{resolved}'")

        return resolved

    def is_protected_file(self, path: str) -> tuple[bool, str]:
        """
        Check if a file is protected (important/sensitive).

        Returns:
            (is_protected, reason) — True + reason if file needs approval
        """
        resolved = Path(path)
        filename = resolved.name.lower()
        extension = resolved.suffix.lower()

        # Check extension
        if extension in self.protected_extensions:
            return True, f"Protected file type: '{extension}' files are sensitive"

        # Check filename patterns
        for pattern in self.protected_patterns:
            if fnmatch.fnmatch(filename, pattern.lower()):
                return True, f"Protected filename pattern: matches '{pattern}'"

        return False, ""

    def needs_approval(self, operation: str, path: str) -> tuple[bool, str]:
        """
        Check if an operation on a path requires user approval.

        Returns:
            (needs_approval, message) — True + message if approval needed
        """
        reasons = []

        # Check 1: Is the operation always-confirm?
        if operation in self.always_confirm_operations:
            reasons.append(f"⚠️ '{operation}' is a destructive operation")

        # Check 2: Is the file protected?
        is_protected, file_reason = self.is_protected_file(path)
        if is_protected:
            reasons.append(f"🔐 {file_reason}")

        if reasons:
            message = (
                f"🔒 APPROVAL REQUIRED for {operation} on '{Path(path).name}':\n"
                + "\n".join(f"  • {r}" for r in reasons)
                + "\n\n🔑 Ask the user for their confirmation PIN to proceed."
            )
            return True, message

        return False, ""

    def verify_pin(self, pin: str) -> bool:
        """Verify the user-provided PIN matches the configured confirmation PIN."""
        if pin.strip() == self.confirm_pin:
            logger.info("🔑 PIN verified successfully")
            return True
        else:
            logger.warning(f"🔑 PIN verification FAILED")
            return False

    def validate_file_size(self, path: Path) -> None:
        """Check that a file doesn't exceed the maximum allowed size."""
        if path.exists() and path.is_file():
            size = path.stat().st_size
            if size > self.max_file_size_bytes:
                raise SecurityError(
                    f"File too large: {size / (1024*1024):.1f} MB "
                    f"(max: {self.max_file_size_bytes / (1024*1024):.1f} MB)"
                )

    @staticmethod
    def _is_subpath(path: Path, parent: Path) -> bool:
        """Check if 'path' is a sub-path of 'parent'."""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def log_operation(self, operation: str, path: str, success: bool = True) -> None:
        """Log a file operation for audit purposes."""
        if self.log_operations:
            status = "✅" if success else "❌"
            logger.info(
                f"{status} [{operation.upper()}] {path} "
                f"at {datetime.now().isoformat()}"
            )

    def get_allowed_directories(self) -> list[str]:
        """Return the list of allowed directories as strings."""
        return [str(d) for d in self.allowed_directories]
