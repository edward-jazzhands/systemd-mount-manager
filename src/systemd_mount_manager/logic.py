# python standard lib
from __future__ import annotations

# import sys
from typing import Sequence
import subprocess
# import os
from pathlib import Path
from dataclasses import dataclass
from enum import StrEnum
from textwrap import dedent

# Third party
# from ezpubsub import Signal, SignalError



# Configuration
MOUNT_UNIT = r"mnt-truenas\x2dtailnet-brents\x2ddata.mount"
AUTOMOUNT_UNIT = r"mnt-truenas\x2dtailnet-brents\x2ddata.automount"
# MOUNT_UNIT_ESCAPED = r"mnt-truenas\\x2dtailnet-brents\\x2ddata.mount"
# AUTOMOUNT_UNIT_ESCAPED = r"mnt-truenas\\x2dtailnet-brents\\x2ddata.automount"
MOUNT_POINT = "/mnt/truenas-tailnet/brents-data"
SMB_SERVER = "truenas-scale"
SMB_SHARE = "brents-data"
CREDS_FILE = "/etc/smb-creds"


SYSTEMD_PATH: Path = Path("/etc/systemd/system/")
HOME: Path = Path.home()
SMM_PATH: Path = HOME / ".config" / "systemd-mount-manager"
MANAGED_MOUNTS_DIR: Path = SMM_PATH / "managed-mounts"


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


def run_command(
    cmd: Sequence[str],
) -> subprocess.CompletedProcess[str]:

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result
    except Exception as e:
        raise e


def create_mount_file(mount_payload: MountPayload) -> str:
    """
    Returns:
        str: Mount file name produced by systemd-escape if the file is created successfully
    Raises:
        Exception: if error while creating the file
    """
    
    mount_string = dedent(f"""\
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
    """)

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
    output_path = MANAGED_MOUNTS_DIR / mountfile_name

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
    src_mount: Path = MANAGED_MOUNTS_DIR / mount_unit
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
        src_unit: Path = MANAGED_MOUNTS_DIR / unit
        run_command(["ln", "-sf", str(src_unit), str(SYSTEMD_PATH)])

    # Enable only the automount
    run_command(["systemctl", "enable", str(automount_unit)])
