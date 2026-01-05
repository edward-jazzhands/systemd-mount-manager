# python standard lib
from __future__ import annotations

import sys
from typing import Sequence, NamedTuple
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from enum import StrEnum
from textwrap import dedent
from configparser import ConfigParser
from textual import log

# Third party
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


SYSTEMD_PATH: Path = Path("/etc/systemd/system/")
HOME: Path = Path.home()
SMM_PATH: Path = HOME / ".config" / "systemd-mount-manager"
CONFIG_PATH = SMM_PATH / "config.ini"
DEFAULT_MOUNTFILES_DIR: Path = SMM_PATH / "managed-mounts"


class MountType(StrEnum):
    MOUNT_AT_BOOT = "mount"
    MOUNT_LAZILY = "automount"


class MountProtocol(StrEnum):
    SMB = "smb"
    NFS = "nfs"


@dataclass
class Setup:
    problems_found: list[tuple[str, int]]
    dry_run: bool


@dataclass
class MountPayload:
    mount_type: MountType
    mount_path: Path  # example: "/mnt/truenas-tailnet/brents-data"
    description: str
    requires: str
    after: str
    what: str
    where: str
    protocol: MountProtocol
    options: str
    timeout: int
    wanted_by: str


@dataclass
class SettingsPayload:
    managed_mounts_dir: str


class TextualLogWriter:

    def __init__(self) -> None:
        self.buffer: list[str] = []

    def flush(self) -> None:
        "write collected messages to terminal"
        log_string = "".join(self.buffer)
        log(log_string.rstrip("\n"))
        self.buffer = []

    def write(self, message: str) -> None:
        self.buffer.append(message)


_log_writer = TextualLogWriter()

# ==============================================================================#

if not SMM_PATH.exists():
    SMM_PATH.mkdir(parents=True)

config = ConfigParser()
# If this is first run, this file will not exist yet and this will do nothing:
read_files = config.read(CONFIG_PATH)


def get_config() -> ConfigParser:
    "Alias for config"
    return config


def write_default_config(force: bool = False) -> bool:
    """Run this for first time setup. Default configs will be loaded
    into configparser and written to config.ini

    Args:
        force (bool, optional): Force overwrite of existing config file. Defaults to False.
    Raises:
        FileExistsError: if config file already exists and force is False
    Returns:
        bool: True if config file was created, False if it already existed (overwrite)
    """

    configfile = CONFIG_PATH
    config_already_exists = False
    if configfile.exists():
        if not force:
            raise FileExistsError(f"Config file already exists: {configfile}")
        config_already_exists = True

    config["DEFAULT"] = {
        "managed_mounts_dir": DEFAULT_MOUNTFILES_DIR.as_posix(),
    }
    with open(CONFIG_PATH, "w") as configfile:
        config.write(configfile)

    # if the config already exists, it means we overwrote it (we return False)
    # if create_already_exists is False, it means we created it. (We return True)
    return not config_already_exists


def change_managed_mounts_dir(new_dir: str) -> None:
    """Change the managed mounts directory"""

    # first convert the string to a path object
    new_path = Path(new_dir)

    config["DEFAULT"]["managed_mounts_dir"] = new_dir.as_posix()

    with open(CONFIG_PATH, "w") as configfile:
        config.write(configfile)


def save_settings(settings_payload: SettingsPayload) -> None:
    """Save settings to config file"""

    # First load new settings into configparser memory

    # Compare old managed mounts dir with new managed mounts dir
    if config["DEFAULT"]["managed_mounts_dir"] != settings_payload.managed_mounts_dir:
        # If the new managed mounts dir is different from the old one,
        change_managed_mounts_dir(new_dir)

    # Use configparser to write to file
    with open(CONFIG_PATH, "w") as configfile:
        config.write(configfile)


def load_settings() -> SettingsPayload:
    """Load settings from config file"""

    return SettingsPayload(managed_mounts_dir=config["DEFAULT"]["managed_mounts_dir"])


def textual_log_config_file() -> None:
    log("Config file:")
    config.write(_log_writer)
    _log_writer.flush()


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


class SystemctlListUnitsLine(NamedTuple):
    """
    Args:
        unit: The unit name.
        load: Reflects whether the unit definition was properly loaded.
        active: The high-level unit activation state, i.e. generalization of SUB.
        sub: The low-level unit activation state, values depend on unit type.
        description: Unit description.
    """

    unit: str
    load: str
    active: str
    sub: str
    description: str


def detect_exising_mounts() -> list[SystemctlListUnitsLine]:
    # First hit systemctl, get giant string returned
    result = run_command(["systemctl", "list-units", "--type=mount", "--all", "--no-legend"])

    # Now normalize the data by converting each line to a SystemctlListUnitsLine obj
    mounts_list_normalized: list[SystemctlListUnitsLine] = []
    for line in result.stdout.splitlines():
        lines_split = line.split()
        if lines_split[0] == "●":
            lines_split.pop(0)
        mounts_list_normalized.append(
            SystemctlListUnitsLine(
                unit=lines_split[0],
                load=lines_split[1],
                active=lines_split[2],
                sub=lines_split[3],
                description=lines_split[4],
            )
        )

    return mounts_list_normalized

    # unit_name = line.split()[0]
    # fragment = run_command(["systemctl", "show", "-p", "FragmentPath", unit_name])
    # if str(DEFAULT_MOUNTFILES_DIR) in fragment.stdout:
    #     # Your mount
    #     pass
    # elif "/run/systemd/generator/" in fragment.stdout:
    #     # fstab mount
    #     pass
    # elif not fragment.stdout.strip().split("=")[1]:
    #     # transient mount
    #     pass


def create_mount_file(mount_payload: MountPayload) -> str:
    """
    Returns:
        str: Mount file name produced by systemd-escape if the file is created successfully
    Raises:
        Exception: if error while creating the file
    """

    mount_string = dedent(
        f"""\
        [Unit]
        Description={mount_payload.description}
        Requires={mount_payload.requires}
        After={mount_payload.after}

        [Mount]
        What={mount_payload.what}
        Where={mount_payload.where}
        Type={mount_payload.protocol}
        Options={mount_payload.options}
        TimeoutSec={mount_payload.timeout}

        [Install]
        WantedBy={mount_payload.wanted_by}
    """
    )

    # Here need to call systemd-escape to get the correct file name
    result = run_command(
        [
            "systemd-escape",
            "-p",
            f"--suffix={mount_payload.mount_type.value}",
            str(mount_payload.mount_path),
        ]
    )
    mountfile_name = result.stdout.strip()
    output_path = DEFAULT_MOUNTFILES_DIR / mountfile_name

    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Overwrite existing file if it exists
        output_path.write_text(mount_string)
    except OSError as e:
        raise RuntimeError(f"Failed to create mount file {output_path}: {e}") from e

    return mountfile_name


def mount_at_boot(mount_unit: str, automount_unit: str) -> None:
    """Mount units must be pre-formatted with systemd-escape:

    mount_unit = r"mnt-server\x2dtailnet-my\x2ddata.mount"
    automount_unit = r"mnt-server\x2dtailnet-my\x2ddata.automount"
    """

    # First disable the lazy mount (This will delete the symlinks in /etc/systemd/system):
    run_command(["systemctl", "disable", str(automount_unit)])

    # Create symlink for only .mount file
    src_mount: Path = DEFAULT_MOUNTFILES_DIR / mount_unit
    run_command(["ln", "-sf", str(src_mount), str(SYSTEMD_PATH)])

    # Enable the .mount file
    run_command(["systemctl", "enable", str(mount_unit)])


def mount_lazily(mount_unit: str, automount_unit: str) -> None:
    """Mount units must be pre-formatted with systemd-escape:

    mount_unit = r"mnt-server\x2dtailnet-my\x2ddata.mount"
    automount_unit = r"mnt-server\x2dtailnet-my\x2ddata.automount"
    """

    # First disable mount at boot (This will delete the symlinks in /etc/systemd/system):
    run_command(["systemctl", "disable", str(mount_unit)])

    # Create symlinks for both (need both for automount)
    for unit in [mount_unit, automount_unit]:
        src_unit: Path = DEFAULT_MOUNTFILES_DIR / unit
        run_command(["ln", "-sf", str(src_unit), str(SYSTEMD_PATH)])

    # Enable only the automount
    run_command(["systemctl", "enable", str(automount_unit)])
