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
import errno
from configparser import ConfigParser

# Third party
from textual import log

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

# ======================================================= #
#                     CONFIG RELATED
# ======================================================= #

config = ConfigParser()
# If this is first run, this file will not exist yet and this will do nothing:
read_files = config.read(CONFIG_PATH)


# A small helper to log current config to Textual console, for debugging
def textual_log_config_file() -> None:
    log("Config file:")
    config.write(_log_writer)
    _log_writer.flush()


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

    # First create the SMM_PATH if it doesn't exist
    if not SMM_PATH.exists():
        SMM_PATH.mkdir(parents=True)

    # Create default mountfiles dir if it doesn't exist
    if not DEFAULT_MOUNTFILES_DIR.exists():
        DEFAULT_MOUNTFILES_DIR.mkdir(parents=True)

    config_already_existed = False
    if CONFIG_PATH.exists():
        if not force:
            raise FileExistsError(f"Config file already exists: {CONFIG_PATH.as_posix()}")
        config_already_existed = True

    # Here create the default config
    config["DEFAULT"] = {
        "managed_mounts_dir": DEFAULT_MOUNTFILES_DIR.as_posix(),
    }
    with open(CONFIG_PATH, "w") as configfile:
        config.write(configfile)

    if config_already_existed:  # then we overwrote it (we return False)
        return False
    else:  # otherwise we created it. (We return True)
        return True


def load_settings() -> SettingsPayload:
    """Load settings from config file. Returns a SettingsPayload object.
    Import the SettingsPayload dataclass for type checking."""

    return SettingsPayload(managed_mounts_dir=config["DEFAULT"]["managed_mounts_dir"])


def change_managed_mounts_dir(new_dir: str, migrate: bool = False):
    """Change the managed mounts directory

    Raises:
        ValueError: if new_dir is the same as the current dir
        OSError: if there is a problem creating the new directory
    """

    # First convert the string to a path object
    new_path = Path(new_dir).resolve()

    # Ensure new dir is not the same as the current dir
    if config["DEFAULT"]["managed_mounts_dir"] == new_dir:
        raise ValueError("New managed mounts dir is the same as the current dir")

    try:
        new_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log.error(e)
        match e.errno:
            case errno.ENOSPC:
                raise OSError("Cannot create directory: No space left on device") from e
            case errno.EROFS:
                raise OSError("Cannot create directory: Read-only filesystem") from e
            case errno.ENAMETOOLONG:
                raise OSError("Cannot create directory: Path name too long") from e
            case errno.EACCES | errno.EPERM:
                raise OSError("Cannot create directory: Permission denied") from e
            case errno.EEXIST:
                raise OSError("Cannot create directory: A file exists at that location") from e
            case errno.ENOTDIR:
                raise OSError("Cannot create directory: Invalid parent path (file in path)") from e
            case errno.ESTALE:
                raise OSError(
                    "Cannot create directory: Network mount is stale or unavailable"
                ) from e
            case errno.EHOSTUNREACH | errno.EHOSTDOWN | errno.ENETUNREACH | errno.ENETDOWN:
                raise OSError("Cannot create directory: Network or host is unreachable") from e
            case errno.EIO:
                raise OSError(
                    "Cannot create directory: I/O error (possible network or disk issue)"
                ) from e
            case _:
                raise OSError(f"Cannot create directory: {e}") from e

    try:
        testfile = new_path / ".testfile"
        testfile.touch()
        testfile.unlink()
    except OSError as e:
        log.error(e)
        match e.errno:
            case errno.ENOSPC:
                raise OSError("Directory change failed: No space left on device") from e
            case errno.EROFS:
                raise OSError("You can't write to that directory: Read-only filesystem") from e
            case errno.EACCES | errno.EPERM:
                raise OSError("You don't have permission to write to that directory") from e
            case _:
                raise OSError(f"Error changing directory: {e}") from e

    if migrate:
        # here add migrate logic when ready
        pass

    # If migration was skipped or successful then we can update the config file
    config["DEFAULT"]["managed_mounts_dir"] = new_dir
    with open(CONFIG_PATH, "w") as configfile:
        config.write(configfile)


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


# ======================================================= #
#                    MOUNTS RELATED
# ======================================================= #

# System Mount Categories

# -.mount (Root Mount)

# - The root filesystem (/)
# - Core to the system, should never be touched by users

# dev-* mounts (Device filesystems)

# - dev-hugepages.mount: Virtual filesystem for large memory pages
# - dev-mqueue.mount: POSIX message queues for inter-process communication
# - Essential kernel interfaces, not user-manageable

# proc-* mounts (Process filesystems)

# - proc-sys-fs-binfmt_misc.mount: Allows registering binary formats (like running Windows .exe files through Wine)
# - Kernel interface, typically left alone

# sys-* mounts (System filesystems)

# - sys-fs-fuse-connections.mount: FUSE filesystem management
# - sys-kernel-config.mount: Kernel module configuration
# - sys-kernel-debug.mount: Kernel debugging info
# - sys-kernel-tracing.mount: Kernel event tracing
# - All kernel interfaces, not user-manageable

# run-* mounts (Runtime filesystems)

# - run-rpc_pipefs.mount: NFS client communication
# - run-user-1000.mount and friends: User session runtime directories
# - Dynamically managed by systemd, shouldn't be manually controlled

# Mount detecting logic flow:

# Get all mount unit files  - systemctl list-unit-files --type=mount
# Get current mount states  - systemctl list-units --type=mount --all --no-legend
# Check for automounts      - systemctl list-units --type=automount --all
# Verify actual mounts      - findmnt or parse /proc/mounts
# Look for fstab mounts     - ls /run/systemd/generator/*.mount
# Look for transient mounts - ls /run/systemd/transient/*.mount
# Use `systemctl show <unit> -p FragmentPath` to get the exact file path


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
    """Runs `systemctl list-units --type=mount --all --no-legend` and returns a list
    of SystemctlListUnitsLine objects."""

    # First hit systemctl, get giant string returned
    result = run_command(["systemctl", "list-units", "--type=mount", "--all", "--no-legend"])

    # Now normalize the data by converting each line to a SystemctlListUnitsLine obj
    mounts_list_normalized: list[SystemctlListUnitsLine] = []
    for line in result.stdout.splitlines():
        lines_split = line.split()
        if lines_split[0] == "●":
            continue
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
