# python standard lib
from __future__ import annotations
import sys
import os
import shutil
from pathlib import Path
from typing import Sequence  # , NamedTuple
import subprocess
import json
from dataclasses import dataclass
import errno
from collections import deque
# from threading import Lock

# from ezpubsub import Signal, SignalError

# Program Constants
SYSTEMD_PATH = Path("/etc/systemd/system/")
APP_NAME = "systemd-mount-manager"


# class UserError(Exception):
#     """Base class for exceptions in Systemd Mount Manager."""


def check_dev_env_var() -> bool:
    """Check if the dev mode env var is set."""
    if dev_env := os.environ.get("SMM_DEV_MODE"):
        if dev_env.lower() in ("1", "true", "yes", "on"):
            return True
    return False

    
@dataclass()
class ErrorStorage:
    """Creates a dataclass that serves as in-memory storage for any
    errors that are caught."""

    error_deque: deque[Exception] 
    "Internal error deque, max size 1000"

    def add_error(self, e: Exception) -> None:
        """Add error to interal deque. deque append is thread-safe."""

        self.error_deque.append(e)

    def get_errors(self) -> list[Exception]:
        """Get all errors as a list."""
        return list(self.error_deque)


error_storage = ErrorStorage(deque(maxlen=1000))
"""Global error storage object. This object is MUTABLE and contains thread-safe
methods utilizing a deque and lock."""


def os_error_logger(e: OSError, action: str, description: str) -> None:
    """Add a note to the exception and store it in the error storage.

    Args:
        e (OSError): The OSError to handle
        action (str): The action being performed
        description (str): The description of the file being acted on
    """

    match e.errno:
        case errno.ENOENT: # no entry
            e.add_note(f"Cannot {action} {description}: File not found")
        case errno.ENOSPC: # no space
            e.add_note(f"Cannot {action} {description}: No space left on device")
        case errno.EROFS: # ROFS = read-only filesystem
            e.add_note(f"Cannot {action} {description}: Read-only filesystem")
        case errno.ENAMETOOLONG:
            e.add_note(f"Cannot {action} {description}: Path name too long")
        case errno.EACCES | errno.EPERM:
            e.add_note(f"Cannot {action} {description}: Permission denied")
        case errno.EEXIST:
            e.add_note(f"Cannot {action} {description}: A file exists at that location")
        case errno.ENOTDIR: # NOTDIR = not a directory
            e.add_note(f"Cannot {action} {description}: Invalid parent path (file in path)")
        case errno.ESTALE:
            e.add_note(f"Cannot {action} {description}: Network mount is stale or unavailable")
        case errno.EHOSTUNREACH | errno.EHOSTDOWN | errno.ENETUNREACH | errno.ENETDOWN:
            e.add_note(f"Cannot {action} {description}: Network or host is unreachable")
        case errno.EIO:
            e.add_note(f"Cannot {action} {description}: I/O error (possible network or disk issue)")
        case _:
            e.add_note(f"Cannot {action} {description}: Unknown error. See traceback.")

    error_storage.add_error(e)



# ======================================================= #
#                SUDO / SUBPROCESS RELATED
# ======================================================= #


def check_sudo_cached() -> bool:
    """Check if sudo credentials are already cached
    Returns:
        bool: True if sudo is cached, False if not
    """
    result = subprocess.run(
        ["sudo", "-n", "true"],  # -n means non-interactive
        capture_output=True,
    )
    return result.returncode == 0


def run_command(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:

    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def run_command_with_sudo(command: str) -> subprocess.CompletedProcess[str]:
    """
    Args:
        command (str): The command to run with sudo.
    Returns:
        subprocess.CompletedProcess[str]: The result of the command
    Raises:
        PermissionError: If sudo is not cached.
    """

    if not check_sudo_cached():
        raise PermissionError("sudo credentials not cached")

    process = subprocess.run(
        ["sudo", "-S", "bash", "-c", command],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return process


def run_command_from_stdin(command: str):
    pass


def input_sudo_password(password: str) -> tuple[bool, str]:
    """Authenticate with sudo and cache credentials.

    Returns:
        tuple: (success, error_message)
    """
    process = subprocess.Popen(
        ["sudo", "-S", "true"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    _, stderr = process.communicate(input=password + "\n")

    if process.returncode == 0:
        return True, ""

    # Parse stderr for useful error messages
    if "incorrect password" in stderr.lower():
        return False, "Incorrect password"
    elif "not in the sudoers file" in stderr.lower():
        return False, "User not authorized for sudo"
    else:
        return False, stderr.strip()


def run_stdio_mode():
    """stdio mode - read commands from stdin, write responses to stdout"""
    while True:
        try:
            line = input()  # or sys.stdin.readline()
            if not line or line.strip() == "quit":
                break

            # Parse and execute command
            result = run_command_from_stdin(line.strip())

            # Send response (JSON is clean)
            print(json.dumps({"status": "ok", "result": result}))
            sys.stdout.flush()  # Important!

        except EOFError:
            break
        except Exception as e:
            print(json.dumps({"status": "error", "error": str(e)}))
            sys.stdout.flush()


def get_editor() -> str:
    """Get the user's preferred editor

    Returns:
        str: The full path to the editor
    """
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")

    if editor:
        editor_cmd = editor.split()[0]
        full_path = shutil.which(editor_cmd)
        if full_path:
            # Return full path, replacing just the command part to preserve args
            return editor.replace(editor_cmd, full_path, 1)

    return (
        shutil.which("nano")
        or shutil.which("nvim")
        or shutil.which("vim")
        or shutil.which("vi")
        or "/usr/bin/vi"  # Absolute fallback
    )
