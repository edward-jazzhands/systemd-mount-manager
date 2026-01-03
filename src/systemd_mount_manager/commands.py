"""commands.py - The single entry point
All interactions with the logic module should go through this file.
Remember: Don't import logic.py directly. Forcing all interactions
to go through the CLICommand function will ensure all interfaces 
(TUI, GUI, and CLI) have a consistent API and are using the same logic.
"""

# NOTE: Right now this file is just bridging the entire logic module.
# This is because we're still in the early stages of development and prototyping.
# For official public release we will want to clean this up and not expose
# every single function unnecessarily.

# You also may have noticed that this "Command Enum" pattern is a bit unconventional.
# A more conventional approach would be to make a class and have all the bridge functions
# be methods of that class.

from enum import Enum
from typing import Any
import subprocess

from systemd_mount_manager import logic

# class SMMCommand(Enum):
#     write_default_config = "write-default-config"
#     textual_log_config_file = "textual-log-config-file"
#     check_sudo_cached = "check-sudo-cached"
#     run_command_with_sudo = "run-command-with-sudo"
#     input_sudo_password = "input-sudo-password"
#     run_stdio_mode = "run-stdio-mode"
#     detect_exising_mounts = "detect-exising-mounts"
#     create_mount_file = "create-mount-file"
#     mount_at_boot = "mount-at-boot"
#     mount_lazily = "mount-lazily"
    


# def CLICommand(smm_command: SMMCommand, **kwargs: Any) -> dict[str, str]:
#     """
#     Single entry point for all interfaces.
    
#     Note that all the function results are converted to strings.
#     This restriction is self-imposed to ensure that the CLI interface will have
#     no issues interacting with the logic module the same way as the UIs.
    
#     Args:
#         command: SMMCommand enum value
#         **kwargs: Command-specific arguments
    
#     Returns:
#         dict with 'status' and 'result' or 'error'
#     """
#     try:
#         match smm_command:
#             case SMMCommand.write_default_config:
#                 result = _write_default_config()
#             case SMMCommand.textual_log_config_file:
#                 result = _textual_log_config_file()
#             case SMMCommand.check_sudo_cached:
#                 result = _check_sudo_cached()
#             case SMMCommand.run_command_with_sudo:
#                 result = _run_command_with_sudo(kwargs['command'])
#             case SMMCommand.input_sudo_password:
#                 result = _input_sudo_password(kwargs['password'])
#             case SMMCommand.run_stdio_mode:
#                 result = _run_stdio_mode()
#             case SMMCommand.detect_exising_mounts:
#                 result = _detect_exising_mounts()
#             case SMMCommand.create_mount_file:
#                 result = _create_mount_file(kwargs['mount_payload'])
#             case SMMCommand.mount_at_boot:
#                 result = _mount_at_boot(kwargs['mount_unit'], kwargs['automount_unit'])
#             case SMMCommand.mount_lazily:
#                 result = _mount_lazily(kwargs['mount_unit'], kwargs['automount_unit'])
#             case _:
#                 return {"status": "error", "error": f"Unknown command: {smm_command}"}
#     except Exception as e:
#         return {"status": "error", "error": str(e)}
       
#     if isinstance(result, subprocess.CompletedProcess):
#         result = result.stdout + result.stderr
#     else:
#         try:
#             result = str(result)
#         except Exception as e:
#             result = f"Could not convert result to string: {e}"
            
#     return {"status": "ok", "result": result}


# Private bridge functions

def _write_default_config() -> bool:
    return logic.write_default_config()

def _textual_log_config_file() -> None: 
    return logic.textual_log_config_file()

def _check_sudo_cached() -> bool:
    return logic.check_sudo_cached()

def _run_command_with_sudo(command: str) -> subprocess.CompletedProcess[str]:
    return logic.run_command_with_sudo(command)

def _input_sudo_password(password: str) -> tuple[bool, str]:
    return logic.input_sudo_password(password)

def _run_stdio_mode() -> None:
    return logic.run_stdio_mode()

def _detect_exising_mounts() -> list[logic.SystemctlListUnitsLine]:
    return logic.detect_exising_mounts()

def _create_mount_file(mount_payload: logic.MountPayload) -> str:
    return logic.create_mount_file(mount_payload)

def _mount_at_boot(mount_unit: str, automount_unit: str) -> None:
    return logic.mount_at_boot(mount_unit, automount_unit)

def _mount_lazily(mount_unit: str, automount_unit: str) -> None:
    return logic.mount_lazily(mount_unit, automount_unit)
