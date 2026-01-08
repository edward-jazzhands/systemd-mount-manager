# python standard lib
from __future__ import annotations
import sys
from typing import Sequence #, NamedTuple
import subprocess
import json
# from pathlib import Path
# from dataclasses import dataclass
# from enum import StrEnum
# from textwrap import dedent
# import errno
# import configparser


# from ezpubsub import Signal, SignalError


# Logic Notes
# Three conceptual layers:

# 1) Pure logic: deterministic transformations, validation, unit generation, parsing,
#    comparison. No I/O, no state, no privileges.
#    Pure logic is imported freely by your own code.

# 2) System interaction: filesystem writes, symlinks, sudo, systemctl, journalctl,
#    discovery probes, network introspection.
#    Anything that causes side effects, privilege escalation, or persistent system change
#    goes through the CLI boundary.

# 3) Interfaces: CLI, TUI, GUI.
#    The CLI becomes the authoritative orchestrator of stateful operations.


# If skipping the CLI would allow an interface to bypass safety, consistency, or
# privilege rules, it should go through the CLI.

# If skipping the CLI would only avoid recomputing a pure value, importing
# the function directly is fine.


# # Configuration
# MOUNT_UNIT = r"mnt-truenas\x2dtailnet-brents\x2ddata.mount"
# AUTOMOUNT_UNIT = r"mnt-truenas\x2dtailnet-brents\x2ddata.automount"
# # MOUNT_UNIT_ESCAPED = r"mnt-truenas\\x2dtailnet-brents\\x2ddata.mount"
# # AUTOMOUNT_UNIT_ESCAPED = r"mnt-truenas\\x2dtailnet-brents\\x2ddata.automount"
# MOUNT_POINT = "/mnt/truenas-tailnet/brents-data"
# SMB_SERVER = "truenas-scale"
# SMB_SHARE = "brents-data"
# CREDS_FILE = "/etc/smb-creds"


# SYSTEMD_PATH: Path = Path("/etc/systemd/system/")
# HOME: Path = Path.home()
# SMM_PATH: Path = HOME / ".config" / "systemd-mount-manager"
# CONFIG_PATH = SMM_PATH / "config.ini"
# DEFAULT_MOUNTFILES_DIR: Path = SMM_PATH / "managed-mounts"


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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result
    except Exception as e:
        raise e


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
