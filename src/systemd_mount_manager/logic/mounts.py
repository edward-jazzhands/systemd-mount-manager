# python standard lib
from __future__ import annotations

# import sys
from typing import NamedTuple, TypedDict, NotRequired

# import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from enum import StrEnum

# from textwrap import dedent
# import errno
import configparser

# Third party
# import rich.rule
from textual import log
from rich.text import Text

# Local
import systemd_mount_manager.logic as logic

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


SYSTEMD_PATH: Path = Path("/etc/systemd/system/")
HOME: Path = Path.home()
SMM_PATH: Path = HOME / ".config" / "systemd-mount-manager"
CONFIG_PATH = SMM_PATH / "config.ini"
DEFAULT_MOUNTFILES_DIR: Path = SMM_PATH / "managed-mounts"


class MountType(StrEnum):
    MOUNT_AT_BOOT = "Mount at boot"
    AUTOMOUNT = "Mount on demand"


class MountProtocol(StrEnum):
    SMB = "smb"
    NFS = "nfs"


class MountTuple(NamedTuple):
    """
    Args:
        unit: The unit name.
        load: Reflects whether the unit definition was properly loaded.
        active: The high-level unit activation state, i.e. generalization of SUB.
        sub: The low-level unit activation state, values depend on unit type.
        description: Unit description.
    """

    mount_type: MountType
    unit: str
    load: str
    active: str
    sub: str
    description: str


class MountDict(TypedDict):
    unit: str
    load: str
    active: str
    sub: str
    description: str


def detect_all_systemd_mounts() -> list[MountTuple]:

    # systemctl list-units --type=mount --no-legend --all
    # systemctl list-units --type=automount --no-legend --all

    # First hit systemctl, get json returned
    try:
        result_mounts = logic.core.run_command(
            ["systemctl", "list-units", "--type=mount", "--all", "--output=json"]
        )
        result_automounts = logic.core.run_command(
            ["systemctl", "list-units", "--type=automount", "--all", "--output=json"]
        )
    except OSError as e:
        raise OSError("systemctl command failed") from e

    result_mounts_json: list[MountDict] = json.loads(result_mounts.stdout)
    result_automounts_json: list[MountDict] = json.loads(result_automounts.stdout)

    result_mounts_tuples = [
        MountTuple(
            mount_type=MountType.MOUNT_AT_BOOT,
            unit=entry["unit"],
            load=entry["load"],
            active=entry["active"],
            sub=entry["sub"],
            description=entry["description"],
        )
        for entry in result_mounts_json
        if not entry["load"].startswith("not-found")
    ]
    result_automounts_tuples = [
        MountTuple(
            mount_type=MountType.AUTOMOUNT,
            unit=entry["unit"],
            load=entry["load"],
            active=entry["active"],
            sub=entry["sub"],
            description=entry["description"],
        )
        for entry in result_automounts_json
        if not entry["load"].startswith("not-found")
    ]
    return result_mounts_tuples + result_automounts_tuples


@dataclass
class ManagedMountUnitSection:
    description: str
    requires: str | None
    after: str | None


@dataclass
class ManagedMountMountSection:
    what: str
    where: str
    type: str
    options: str
    timeoutsec: str


@dataclass
class ManagedMountAutomountSection:
    where: str
    timeoutidlesec: str


@dataclass
class ManagedMountInstallSection:
    wantedby: str


@dataclass
class ManagedMountData:
    unit: ManagedMountUnitSection
    install: ManagedMountInstallSection
    mount: ManagedMountMountSection | ManagedMountAutomountSection


def list_managed_mounts() -> list[Path]:
    """Scans the managed mounts directory and returns a list of Path objects
    representing .mount and .automount files"""

    # dir_path = Path(logic.config.config["DEFAULT"]["managed_mounts_dir"])
    dir_path = DEFAULT_MOUNTFILES_DIR
    mount_files = list(dir_path.glob("*.mount"))
    automount_files = list(dir_path.glob("*.automount"))
    return mount_files + automount_files


def list_managed_mounts_data() -> list[ManagedMountData]:

    # 1) Scan managed mounts directory for files

    # 2) For each mount file, we need to know:

    # Do symlinks exist and point to the right place?
    # os.path.islink("/etc/systemd/system/unit.automount")
    # os.readlink("/etc/systemd/system/unit.automount") matches expected source

    # Does systemd know about it?
    # Parse systemctl list-unit-files --type=automount
    # Look for your unit (should show linked or enabled)

    # Is it enabled for boot?
    # Check STATE column from list-unit-files (should be enabled for automounts)
    # Or use systemctl is-enabled <unit>

    # Is it currently loaded/active?
    # Parse systemctl list-units --type=automount
    # Check ACTIVE and SUB columns
    # Or use systemctl is-active <unit>

    # Are the symlink and systemd in sync?
    # If symlink exists but unit not in list-unit-files → need systemctl daemon-reload
    # If unit shows linked but should be enabled → need systemctl enable

    mounts = list_managed_mounts()
    mountparser = configparser.ConfigParser()
    successful_reads = 0
    successful_normalized = 0
    mounts_data: list[ManagedMountData] = []
    for mount in mounts:

        mountparser.clear()
        try:
            mountparser.read(mount)
        except configparser.Error as e:
            log.error(f"Error reading {mount}: {e}")
            continue
        successful_reads += 1

        if "Automount" in mountparser.sections():
            mount_section = ManagedMountAutomountSection(
                where=mountparser.get("Automount", "Where"),
                timeoutidlesec=mountparser.get("Automount", "TimeoutIdleSec"),
            )
        else:
            mount_section = ManagedMountMountSection(
                what=mountparser.get("Mount", "What"),
                where=mountparser.get("Mount", "Where"),
                type=mountparser.get("Mount", "Type"),
                options=mountparser.get("Mount", "Options"),
                timeoutsec=mountparser.get("Mount", "TimeoutSec"),
            )

        mounts_data.append(
            ManagedMountData(
                unit=ManagedMountUnitSection(
                    description=mountparser.get("Unit", "Description"),
                    requires=mountparser.get("Unit", "Requires", fallback=None),
                    after=mountparser.get("Unit", "After", fallback=None),
                ),
                install=ManagedMountInstallSection(
                    wantedby=mountparser.get("Install", "WantedBy"),
                ),
                mount=mount_section,
            )
        )
        successful_normalized += 1

    log(f"Successfully read {successful_reads} and normalized {successful_normalized} mount files")
    return mounts_data


# @dataclass
# class MountPayload:
#     mount_type: MountType
#     mount_path: Path  # example: "/mnt/truenas-tailnet/brents-data"
#     description: str
#     requires: str
#     after: str
#     what: str
#     where: str
#     protocol: MountProtocol
#     options: str
#     timeout: int
#     wanted_by: str


# def create_mount_file(mount_payload: MountPayload) -> str:
#     """
#     Returns:
#         str: Mount file name produced by systemd-escape if the file is created successfully
#     Raises:
#         Exception: if error while creating the file
#     """

#     mount_string = dedent(
#         f"""\
#         [Unit]
#         Description={mount_payload.description}
#         Requires={mount_payload.requires}
#         After={mount_payload.after}

#         [Mount]
#         What={mount_payload.what}
#         Where={mount_payload.where}
#         Type={mount_payload.protocol}
#         Options={mount_payload.options}
#         TimeoutSec={mount_payload.timeout}

#         [Install]
#         WantedBy={mount_payload.wanted_by}
#     """
#     )

#     # Here need to call systemd-escape to get the correct file name
#     result = logic.core.run_command(
#         [
#             "systemd-escape",
#             "-p",
#             f"--suffix={mount_payload.mount_type.value}",
#             str(mount_payload.mount_path),
#         ]
#     )
#     mountfile_name = result.stdout.strip()
#     output_path = DEFAULT_MOUNTFILES_DIR / mountfile_name

#     try:
#         # Ensure parent directory exists
#         output_path.parent.mkdir(parents=True, exist_ok=True)
#         # Overwrite existing file if it exists
#         output_path.write_text(mount_string)
#     except OSError as e:
#         raise RuntimeError(f"Failed to create mount file {output_path}: {e}") from e

#     return mountfile_name


def mount_at_boot(mount_unit: str, automount_unit: str) -> None:
    """Mount units must be pre-formatted with systemd-escape:

    mount_unit = r"mnt-server\x2dtailnet-my\x2ddata.mount"
    automount_unit = r"mnt-server\x2dtailnet-my\x2ddata.automount"
    """

    # First disable the lazy mount (This will delete the symlinks in /etc/systemd/system):
    logic.core.run_command(["systemctl", "disable", str(automount_unit)])

    # Create symlink for only .mount file
    src_mount: Path = DEFAULT_MOUNTFILES_DIR / mount_unit
    logic.core.run_command(["ln", "-sf", str(src_mount), str(SYSTEMD_PATH)])

    # Enable the .mount file
    logic.core.run_command(["systemctl", "enable", str(mount_unit)])


def mount_lazily(mount_unit: str, automount_unit: str) -> None:
    """Mount units must be pre-formatted with systemd-escape:

    mount_unit = r"mnt-server\x2dtailnet-my\x2ddata.mount"
    automount_unit = r"mnt-server\x2dtailnet-my\x2ddata.automount"
    """

    # First disable mount at boot (This will delete the symlinks in /etc/systemd/system):
    logic.core.run_command(["systemctl", "disable", str(mount_unit)])

    # Create symlinks for both (need both for automount)
    for unit in [mount_unit, automount_unit]:
        src_unit: Path = DEFAULT_MOUNTFILES_DIR / unit
        logic.core.run_command(["ln", "-sf", str(src_unit), str(SYSTEMD_PATH)])

    # Enable only the automount
    logic.core.run_command(["systemctl", "enable", str(automount_unit)])
