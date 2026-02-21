# python standard lib
from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict
if TYPE_CHECKING:
    import logging
import copy
import sys
import enum
import os
import shutil
from pathlib import Path
from typing import Sequence  # , NamedTuple
import subprocess
import json
from dataclasses import dataclass, field
import errno
import queue
from threading import Lock

# from ezpubsub import Signal, SignalError

# Program Constants
SYSTEMD_PATH = Path("/etc/systemd/system/")
APP_NAME = "systemd-mount-manager"
DEFAULT_SYS_CONFIG_DIR = "~/.config"
DEFAULT_SYS_LOGS_DIR = "~/.local/state"

# class UserError(Exception):
#     """Base class for exceptions in Systemd Mount Manager."""


@dataclass()
class StartupResult:
    """TypedDict for startup results"""

    logging: bool
    config: bool
    handler_swap: bool
    dev: bool


def check_dev_env_var() -> bool:
    """Check if the dev mode env var is set."""
    if dev_env := os.environ.get("SMM_DEV_MODE"):
        if dev_env.lower() in ("1", "true", "yes", "on"):
            return True
    return False


@dataclass()
class ErrorStorage:
    """Creates a dataclass that serves as in-memory storage for any
    errors that are caught.

    Args:
        maxsize (int, optional): The max size of the error queue. Defaults to 1000.
    """

    error_list: list[Exception] = field(default_factory=list)
    "Internal error list"

    logger: logging.Logger | None = None
    """ErrorStorage keeps a reference to the desired logger. Add using the
    add_logger method."""

    lock: Lock = field(init=False, default_factory=Lock)

    def add_error(self, e: Exception) -> None:
        """Add error. Thread-safe."""
        with self.lock:
            self.error_list.append(e)

        # During startup, this might receive errors from the log_setup module.
        # If that happens then we can't just send it to the logger, its not ready yet.
        if self.logger:
            self.logger.error(str(e))

        # The logger will look into the error storage itself once it has 
        # initialized and log any errors that were saved.

    def get_list_copy(self) -> list[Exception]:
        """Return a copy of the error list"""
        with self.lock:
            return copy.deepcopy(self.error_list)

    def add_logger(self, logger: logging.Logger) -> None:
        """Add a logger to the error storage. Errors will be passed to this logger."""
        self.logger = logger

    @property
    def length(self) -> int:
        """Return the length of the error list"""
        with self.lock:
            return len(self.error_list)

    def __len__(self) -> int:
        """Return the length of the error list"""
        return self.length


error_storage = ErrorStorage()
"""Global error storage object. This object is mutable, but contains thread-safe
methods utilizing a Lock."""


def os_error_logger(e: OSError, action: str, description: str) -> None:
    """Add a note to the exception and store it in the error storage.

    Args:
        e (OSError): The OSError to handle
        action (str): The action being performed
        description (str): The description of the file being acted on
    """

    match e.errno:
        case errno.ENOENT:  # no entry
            e.add_note(f"Cannot {action} {description}: File not found")
        case errno.ENOSPC:  # no space
            e.add_note(f"Cannot {action} {description}: No space left on device")
        case errno.EROFS:  # ROFS = read-only filesystem
            e.add_note(f"Cannot {action} {description}: Read-only filesystem")
        case errno.ENAMETOOLONG:
            e.add_note(f"Cannot {action} {description}: Path name too long")
        case errno.EACCES | errno.EPERM:
            e.add_note(f"Cannot {action} {description}: Permission denied")
        case errno.EEXIST:
            e.add_note(f"Cannot {action} {description}: A file exists at that location")
        case errno.ENOTDIR:  # NOTDIR = not a directory
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


class XDGDirectory(enum.StrEnum):
    """The valid env vars this program is concerned with for XDG paths.
    XDG spec env vars must be absolute paths.

    CONFIG: "XDG_CONFIG_HOME" - For config files
    STATE: "XDG_STATE_HOME" - For logs
    """

    CONFIG = "XDG_CONFIG_HOME"
    STATE = "XDG_STATE_HOME"


def _get_dir_following_xdg_spec(xdg_env_var: XDGDirectory) -> Path:
    """
    Get a Path representing one of the supported directories following XDG spec.

    Priority:
    1. {xdg_env_var}/systemd-mount-manager (if the {xdg_env_var} is set)
    2. Default path (fallback)

    Args:
        xdg_env_var (XDGDirectory): The XDG environment variable to use
    Returns:
        Path: The absolute path INCLUDING the app name
    """

    # xdg_env_var takes priority if set and valid
    if xdg_dir := os.getenv(xdg_env_var):
        # logger.debug(f"XDG env var {xdg_env_var} set to {xdg_dir}")
        xdg_path = Path(xdg_dir.strip())
        if xdg_path.is_absolute():
            return Path(xdg_dir.strip()) / APP_NAME

    # If the XDG env var is not set or valid, then fallback to defaults.

    if xdg_env_var == XDGDirectory.CONFIG:
        dir_path = Path(DEFAULT_SYS_CONFIG_DIR).expanduser() / APP_NAME
    elif xdg_env_var == XDGDirectory.STATE:
        dir_path = Path(DEFAULT_SYS_LOGS_DIR).expanduser() / APP_NAME

    # logger.debug(f"Using {dir_path} as config dir")
    return dir_path

# @dataclass()
# class StartupResultStorage:
#     """ """

#     results: dict[str, bool] = field(init=False, default_factory=dict)
#     lock: Lock = field(init=False, default_factory=Lock)

#     def add_result(self, result: str, value: bool) -> None:
#         """Add a result to the storage"""
#         with self.lock:
#             self.results[result] = value

#     def get_result(self, result: str) -> bool:
#         """Get a result from the storage"""
#         with self.lock:
#             return self.results[result]

# startup_result_storage = StartupResultStorage()
# """Global startup result storage object. This object is mutable, but contains thread-safe
# methods utilizing a Lock."""


# === ABOUT PYDANTIC ERRORS === #

# Pydantic contains this nifty `errors()` method that returns a list of errors
# that were encountered during validation. Note that this is a list of
# `ErrorDetails` objects, which are a dict with the following keys:

# - `type`: The type of error that occurred, this is an identifier designed for
#   programmatic use that will change rarely or never.
# - `loc`: Tuple of (str, int) identifying where in the schema the error occurred.
#   the str is the name of the field (the key), and the int is {???}
# - `msg`: A human readable error message.
# - `input`: The input data at this `loc` that caused the error.
# - `ctx`: Values which are required to render the error message, and could hence be useful in
#   rendering custom error messages. Also useful for passing custom error data forward.
# - `url`: The documentation URL giving information about the error. No URL is available if
#   a [`PydanticCustomError`][pydantic_core.PydanticCustomError] is used.

# ABOUT 'loc'

# The loc tuple represents the path to the field that failed validation, tracing through
# your nested data structure from the root down to the exact problem location. Each
# element in the tuple is one step deeper into the nesting. For simple fields, it's just
# the field name like ('username',). For nested models, it shows the path through field
# names like ('username', 'address', 'zip_code'). When validating sequences like lists,
# an integer  index appears in the path to indicate which element failed, like
# ('items', 2, 'price') for an error in the third item's price field.


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
