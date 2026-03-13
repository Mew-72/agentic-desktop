"""
Secure File Management MCP Server
===================================

An MCP (Model Context Protocol) server that provides AI agents with
controlled, safe access to the local file system.

SECURITY: Only directories listed in config.json or ALLOWED_DIRECTORIES
env var can be accessed. All paths are validated to prevent traversal attacks.

Tools provided:
  - list_files      : List directory contents
  - read_file       : Read file content
  - write_file      : Create/write files
  - delete_file     : Delete files
  - rename_file     : Rename/move files
  - create_directory: Create directories
  - get_file_info   : Get file metadata
  - search_files    : Search files by pattern
"""

import os
import sys
import stat
import fnmatch
from datetime import datetime
from pathlib import Path

# Ensure the src/ directory is on sys.path so 'security' module can be found
# even when this script is launched as a subprocess from a different working dir
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from mcp.server.fastmcp import FastMCP

from security import PathValidator, SecurityError

# ──────────────────────────────────────────────
# Initialize
# ──────────────────────────────────────────────

validator = PathValidator()

mcp = FastMCP(
    "Secure File Manager",
    instructions=(
        "This server provides secure file management tools. "
        "All file operations are restricted to pre-approved directories only. "
        f"Allowed directories: {validator.get_allowed_directories()}"
    ),
)


# ──────────────────────────────────────────────
# Tool 1: List Files
# ──────────────────────────────────────────────

@mcp.tool()
def list_files(path: str, recursive: bool = False) -> str:
    """
    List files and directories at the given path.

    Args:
        path: Directory path to list
        recursive: If True, list all files recursively (default: False)

    Returns:
        Formatted list of files and directories with their types
    """
    try:
        resolved = validator.validate_path(path, must_exist=True)

        if not resolved.is_dir():
            return f"Error: '{path}' is not a directory"

        entries = []
        if recursive:
            for root, dirs, files in os.walk(resolved):
                root_path = Path(root)
                for d in sorted(dirs):
                    rel = (root_path / d).relative_to(resolved)
                    entries.append(f"📁 {rel}/")
                for f in sorted(files):
                    rel = (root_path / f).relative_to(resolved)
                    size = (root_path / f).stat().st_size
                    entries.append(f"📄 {rel}  ({_format_size(size)})")
        else:
            for item in sorted(resolved.iterdir()):
                if item.is_dir():
                    entries.append(f"📁 {item.name}/")
                else:
                    size = item.stat().st_size
                    entries.append(f"📄 {item.name}  ({_format_size(size)})")

        validator.log_operation("list_files", path)

        if not entries:
            return f"Directory '{path}' is empty"

        header = f"Contents of '{resolved}' ({len(entries)} items):\n"
        return header + "\n".join(entries)

    except SecurityError as e:
        return f"🚫 Security Error: {e}"
    except FileNotFoundError as e:
        return f"❌ Not Found: {e}"
    except PermissionError:
        return f"🔒 Permission Denied: Cannot access '{path}'"
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Tool 2: Read File
# ──────────────────────────────────────────────

@mcp.tool()
def read_file(path: str, max_lines: int = 0) -> str:
    """
    Read the content of a file.

    Args:
        path: Path to the file to read
        max_lines: Maximum number of lines to read (0 = all lines)

    Returns:
        The file content as text
    """
    try:
        resolved = validator.validate_path(path, must_exist=True)

        if not resolved.is_file():
            return f"Error: '{path}' is not a file"

        validator.validate_file_size(resolved)

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            if max_lines > 0:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"\n... (truncated after {max_lines} lines)")
                        break
                    lines.append(line)
                content = "".join(lines)
            else:
                content = f.read()

        validator.log_operation("read_file", path)
        size = resolved.stat().st_size
        return (
            f"📄 File: {resolved.name} ({_format_size(size)})\n"
            f"{'─' * 40}\n"
            f"{content}"
        )

    except SecurityError as e:
        return f"🚫 Security Error: {e}"
    except FileNotFoundError as e:
        return f"❌ Not Found: {e}"
    except PermissionError:
        return f"🔒 Permission Denied: Cannot read '{path}'"
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Tool 3: Write File
# ──────────────────────────────────────────────

@mcp.tool()
def write_file(path: str, content: str, append: bool = False) -> str:
    """
    Write content to a file. Creates the file if it doesn't exist.

    Args:
        path: Path to the file to write
        content: The text content to write
        append: If True, append to file instead of overwriting (default: False)

    Returns:
        Success or error message
    """
    try:
        resolved = validator.validate_path(path)

        # Ensure parent directory exists
        resolved.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        action = "Appended to" if append else "Written to"

        with open(resolved, mode, encoding="utf-8") as f:
            f.write(content)

        validator.log_operation("write_file", path)
        size = resolved.stat().st_size
        return (
            f"✅ {action} file: {resolved}\n"
            f"   Size: {_format_size(size)}"
        )

    except SecurityError as e:
        return f"🚫 Security Error: {e}"
    except PermissionError:
        return f"🔒 Permission Denied: Cannot write to '{path}'"
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Tool 4: Delete File
# ──────────────────────────────────────────────

@mcp.tool()
def delete_file(path: str) -> str:
    """
    Delete a file or empty directory.

    Args:
        path: Path to the file or empty directory to delete

    Returns:
        Success or error message
    """
    try:
        resolved = validator.validate_path(path, must_exist=True)

        if resolved.is_file():
            resolved.unlink()
            validator.log_operation("delete_file", path)
            return f"✅ Deleted file: {resolved}"
        elif resolved.is_dir():
            contents = list(resolved.iterdir())
            if contents:
                return (
                    f"⚠️ Cannot delete non-empty directory: '{path}' "
                    f"({len(contents)} items inside). "
                    f"Delete contents first for safety."
                )
            resolved.rmdir()
            validator.log_operation("delete_directory", path)
            return f"✅ Deleted empty directory: {resolved}"
        else:
            return f"Error: '{path}' is not a file or directory"

    except SecurityError as e:
        return f"🚫 Security Error: {e}"
    except FileNotFoundError as e:
        return f"❌ Not Found: {e}"
    except PermissionError:
        return f"🔒 Permission Denied: Cannot delete '{path}'"
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Tool 5: Rename / Move File
# ──────────────────────────────────────────────

@mcp.tool()
def rename_file(old_path: str, new_path: str) -> str:
    """
    Rename or move a file/directory. Both paths must be in allowed directories.

    Args:
        old_path: Current path of the file/directory
        new_path: New path for the file/directory

    Returns:
        Success or error message
    """
    try:
        resolved_old = validator.validate_path(old_path, must_exist=True)
        resolved_new = validator.validate_path(new_path)

        if resolved_new.exists():
            return f"⚠️ Destination already exists: '{new_path}'"

        resolved_new.parent.mkdir(parents=True, exist_ok=True)

        resolved_old.rename(resolved_new)
        validator.log_operation("rename_file", f"{old_path} → {new_path}")
        return (
            f"✅ Renamed/moved:\n"
            f"   From: {resolved_old}\n"
            f"   To:   {resolved_new}"
        )

    except SecurityError as e:
        return f"🚫 Security Error: {e}"
    except FileNotFoundError as e:
        return f"❌ Not Found: {e}"
    except PermissionError:
        return f"🔒 Permission Denied: Cannot rename '{old_path}'"
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Tool 6: Create Directory
# ──────────────────────────────────────────────

@mcp.tool()
def create_directory(path: str) -> str:
    """
    Create a new directory (including parent directories if needed).

    Args:
        path: Path of the directory to create

    Returns:
        Success or error message
    """
    try:
        resolved = validator.validate_path(path)

        if resolved.exists():
            if resolved.is_dir():
                return f"ℹ️ Directory already exists: {resolved}"
            else:
                return f"⚠️ A file already exists at this path: {resolved}"

        resolved.mkdir(parents=True, exist_ok=True)
        validator.log_operation("create_directory", path)
        return f"✅ Created directory: {resolved}"

    except SecurityError as e:
        return f"🚫 Security Error: {e}"
    except PermissionError:
        return f"🔒 Permission Denied: Cannot create directory '{path}'"
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Tool 7: Get File Info
# ──────────────────────────────────────────────

@mcp.tool()
def get_file_info(path: str) -> str:
    """
    Get detailed metadata about a file or directory.

    Args:
        path: Path to the file or directory

    Returns:
        Formatted metadata (size, dates, type, permissions)
    """
    try:
        resolved = validator.validate_path(path, must_exist=True)
        file_stat = resolved.stat()

        file_type = "Directory" if resolved.is_dir() else "File"
        size = _format_size(file_stat.st_size)
        created = datetime.fromtimestamp(file_stat.st_ctime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        modified = datetime.fromtimestamp(file_stat.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        accessed = datetime.fromtimestamp(file_stat.st_atime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Get permissions in a readable format
        mode = file_stat.st_mode
        perms = []
        if mode & stat.S_IRUSR:
            perms.append("read")
        if mode & stat.S_IWUSR:
            perms.append("write")
        if mode & stat.S_IXUSR:
            perms.append("execute")

        info_lines = [
            f"📊 File Info: {resolved}",
            f"{'─' * 40}",
            f"  Type:       {file_type}",
            f"  Size:       {size}",
            f"  Created:    {created}",
            f"  Modified:   {modified}",
            f"  Accessed:   {accessed}",
            f"  Permissions: {', '.join(perms) if perms else 'none'}",
        ]

        if resolved.is_file():
            info_lines.append(f"  Extension:  {resolved.suffix or 'none'}")

        if resolved.is_dir():
            count = len(list(resolved.iterdir()))
            info_lines.append(f"  Contents:   {count} items")

        validator.log_operation("get_file_info", path)
        return "\n".join(info_lines)

    except SecurityError as e:
        return f"🚫 Security Error: {e}"
    except FileNotFoundError as e:
        return f"❌ Not Found: {e}"
    except PermissionError:
        return f"🔒 Permission Denied: Cannot access '{path}'"
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Tool 8: Search Files
# ──────────────────────────────────────────────

@mcp.tool()
def search_files(directory: str, pattern: str, max_results: int = 50) -> str:
    """
    Search for files matching a pattern within a directory.

    Args:
        directory: Directory to search in
        pattern: Glob pattern to match (e.g., '*.py', 'test_*', '*.txt')
        max_results: Maximum number of results to return (default: 50)

    Returns:
        List of matching files with their paths and sizes
    """
    try:
        resolved = validator.validate_path(directory, must_exist=True)

        if not resolved.is_dir():
            return f"Error: '{directory}' is not a directory"

        matches = []
        count = 0

        for root, dirs, files in os.walk(resolved):
            for filename in files:
                if fnmatch.fnmatch(filename, pattern):
                    filepath = Path(root) / filename
                    rel_path = filepath.relative_to(resolved)
                    size = filepath.stat().st_size
                    matches.append(f"  📄 {rel_path}  ({_format_size(size)})")
                    count += 1
                    if count >= max_results:
                        break
            if count >= max_results:
                break

        validator.log_operation("search_files", f"{directory} (pattern: {pattern})")

        if not matches:
            return f"No files matching '{pattern}' found in '{directory}'"

        header = f"🔍 Search results for '{pattern}' in '{resolved}' ({len(matches)} matches):\n"
        result = header + "\n".join(matches)
        if count >= max_results:
            result += f"\n  ... (limited to {max_results} results)"
        return result

    except SecurityError as e:
        return f"🚫 Security Error: {e}"
    except FileNotFoundError as e:
        return f"❌ Not Found: {e}"
    except PermissionError:
        return f"🔒 Permission Denied: Cannot search '{directory}'"
    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Tool 9: Open File or App
# ──────────────────────────────────────────────

@mcp.tool()
def open_file_or_app(path_or_name: str) -> str:
    """
    Open any file or application from the system in its default app (e.g. PDF in Acrobat, 'calc' to open calculator).
    This is NOT restricted to allowed directories.

    Args:
        path_or_name: Path to the file or name of the app to open

    Returns:
        Success or error message
    """
    try:
        os.startfile(path_or_name)
        validator.log_operation("open_file_or_app", path_or_name)
        return f"✅ Opened '{path_or_name}' successfully."

    except Exception as e:
        return f"❌ Error: {e}"


# ──────────────────────────────────────────────
# Bonus: Show allowed directories
# ──────────────────────────────────────────────

@mcp.tool()
def get_allowed_directories() -> str:
    """
    Show which directories this server is allowed to access.
    Use this to understand the security boundaries.

    Returns:
        List of allowed directories
    """
    dirs = validator.get_allowed_directories()
    if not dirs:
        return "⚠️ No directories are currently allowed. Update config.json or set ALLOWED_DIRECTORIES env var."
    
    header = "🔐 Allowed Directories:\n"
    lines = [f"  ✅ {d}" for d in dirs]
    return header + "\n".join(lines)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    print("🚀 Starting Secure File Management MCP Server...", file=_sys.stderr)
    print(f"🔐 Allowed directories: {validator.get_allowed_directories()}", file=_sys.stderr)
    print("📡 Transport: stdio (waiting for MCP client connection)", file=_sys.stderr)
    mcp.run(transport="stdio")
