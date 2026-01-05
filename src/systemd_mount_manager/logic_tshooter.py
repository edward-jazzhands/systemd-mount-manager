from __future__ import annotations

# import sys
# from typing import Sequence
import subprocess
from pathlib import Path
from dataclasses import dataclass

# # ANSI color codes
# class Color:
#     RED = "\033[0;31m"
#     GREEN = "\033[0;32m"
#     YELLOW = "\033[1;33m"
#     BLUE = "\033[0;36m"
#     GRAY = "\033[1;30m"
#     ORANGE = "\033[0;33m"
#     NC = "\033[0m"  # No Color


# Configuration
MOUNT_UNIT = r"mnt-truenas\x2dtailnet-brents\x2ddata.mount"
AUTOMOUNT_UNIT = r"mnt-truenas\x2dtailnet-brents\x2ddata.automount"
MOUNT_UNIT_ESCAPED = r"mnt-truenas\\x2dtailnet-brents\\x2ddata.mount"
AUTOMOUNT_UNIT_ESCAPED = r"mnt-truenas\\x2dtailnet-brents\\x2ddata.automount"
MOUNT_POINT = "/mnt/truenas-tailnet/brents-data"
SMB_SERVER = "truenas-scale"
SMB_SHARE = "brents-data"
CREDS_FILE = "/etc/smb-creds"


SYSTEMD_PATH: Path = Path("/etc/systemd/system/")
# SCRIPT_DIR: Path = Path(__file__).parent.resolve()
HOME: Path = Path.home()


@dataclass
class TroubleshooterData:
    problems_found: list[tuple[str, int]]
    automount_path_exists: bool


def run_command(
    cmd: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CalledProcessError:
    """Run a shell command and return result"""

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        return e
    else:
        return result


def check_unit_files() -> None:
    """[1] Check if systemd unit files exist"""

    mount_path = Path(f"/etc/systemd/system/{MOUNT_UNIT}")
    automount_path = Path(f"/etc/systemd/system/{AUTOMOUNT_UNIT}")

    # print_status(mount_path.exists(), "Mount unit file exists?")
    if not mount_path.exists():
        TroubleshooterData.problems_found.append(
            ("Mount unit file NOT found in /etc/systemd/system/", 1)
        )

    # print_status(automount_path.exists(), "Automount unit file exists?")
    if not automount_path.exists():
        TroubleshooterData.automount_path_exists = False
    else:
        TroubleshooterData.automount_path_exists = True


def check_enabled_units() -> None:
    """[2] Check which units are enabled"""

    is_one_enabled = False

    # Mount at boot
    mount_enabled_result = run_command(f"systemctl is-enabled {MOUNT_UNIT_ESCAPED}")
    mount_enabled = mount_enabled_result.returncode == 0
    # print_status(mount_enabled, "Mount at boot unit enabled?")
    if mount_enabled:
        is_one_enabled = True

    # Automount
    automount_enabled_result = run_command(f"systemctl is-enabled {AUTOMOUNT_UNIT_ESCAPED}")
    automount_enabled = automount_enabled_result.returncode == 0
    # print_status(automount_enabled, "Auto-mount at boot unit enabled?")
    if automount_enabled:
        is_one_enabled = True
        if not TroubleshooterData.automount_path_exists:
            TroubleshooterData.problems_found.append(
                ("Automount unit is enabled, but automount path does NOT exist", 2)
            )

    if not is_one_enabled:
        TroubleshooterData.problems_found.append(
            ("Neither automount nor mount at boot unit is enabled in systemctl", 2)
        )


# def show_systemctl_dashboard() -> None:
#     """[3] Display the systemctl status dashboard for the mounts."""

#     mount_status_result = run_command(
#         f"systemctl status {MOUNT_UNIT_ESCAPED} --no-pager 2>&1",
#     )
#     # print("\n".join(mount_status_result.stdout.split("\n")[:5]))

#     automount_status_result = run_command(
#         f"systemctl status {AUTOMOUNT_UNIT_ESCAPED} --no-pager 2>&1",
#     )
#     # print("\n".join(automount_status_result.stdout.split("\n")[:5]))


def check_tailscale() -> None:
    """[4] Check Tailscale status"""

    # First check if tailscale command exists and is connected
    tailscale_installed_result = run_command("command -v tailscale")
    tailscale_installed = tailscale_installed_result.returncode == 0
    # print_status(tailscale_installed, "Tailscale installed?")
    if not tailscale_installed:
        TroubleshooterData.problems_found.append(
            ("Tailscale command NOT found. Do you have Tailscale installed?", 4)
        )
        return

    # Tailscale is installed, check if running:
    tailscaled_active_result = run_command("systemctl is-active tailscaled.service")
    tailscaled_active = tailscaled_active_result.returncode == 0
    # print_status(tailscaled_active, "Is Tailscaled running?")
    if not tailscaled_active:
        TroubleshooterData.problems_found.append(("Tailscaled is NOT running", 4))
        return

    # Tailscale is running, check if connected:
    tailscale_status = run_command("tailscale status 2>&1")
    is_connected = tailscale_status.returncode == 0
    # print_status(is_connected, "Tailscale is connected?")
    if not is_connected:
        TroubleshooterData.problems_found.append(("Tailscale is NOT connected", 4))
        return

    # Tailscale is connected, check if destination is also connected:
    output = tailscale_status.stdout.strip().split("\n")
    found_smb_server = False
    smb_server_online = False
    for line in output:
        if SMB_SERVER in line:
            found_smb_server = True
            if "offline" not in line:
                smb_server_online = True

    # print_status(found_smb_server, "Tailscaled says your SMB server exists in your tailnet?")
    if not found_smb_server:
        TroubleshooterData.problems_found.append(
            (f"Tailscaled says {SMB_SERVER} does NOT exist in your tailnet", 4)
        )

    # print_status(smb_server_online, "Tailscaled says your SMB server is online?")
    if not smb_server_online:
        TroubleshooterData.problems_found.append((f"Tailscaled says {SMB_SERVER} is offline", 4))


def check_mount_point() -> None:
    """[5] Check if mount point directory exists"""

    try:
        mount_path = Path(MOUNT_POINT)
        exists = mount_path.exists() and mount_path.is_dir()
    except Exception as e:
        TroubleshooterData.problems_found.append((f"Error: {e}", 5))
        return
    else:
        # print_status(exists, f"Mount point directory exists?: {MOUNT_POINT}")
        if not exists:
            TroubleshooterData.problems_found.append(
                (f"Mount point directory does NOT exist: {MOUNT_POINT}", 5)
            )


def check_credentials() -> None:
    """[6] Check credentials file"""

    creds_path = Path(CREDS_FILE)
    exists = creds_path.exists()

    # print_status(exists, f"Credentials file exists?: {CREDS_FILE}")
    if exists:
        # Check permissions
        stat_result = run_command(f"stat -c %a {CREDS_FILE}")
        perms = stat_result.stdout.strip()

        is_secure = perms in ["600", "400"]
        # print_status(is_secure, f"Permissions are secure?: {perms}")
        if not is_secure:
            TroubleshooterData.problems_found.append(
                (f"Permissions may be too open: {perms} (should be 600 or 400)", 6)
            )
    else:
        TroubleshooterData.problems_found.append(("Credentials file NOT found", 6))


def check_network() -> None:
    """[7] Check network connectivity to TrueNAS"""

    ping_result = run_command(f"ping -c 1 -W 2 {SMB_SERVER} 2>&1")
    can_ping = ping_result.returncode == 0

    # print_status(can_ping, f"Can ping {SMB_SERVER}?")
    if can_ping:
        # Extract time from ping output
        for line in ping_result.stdout.split("\n"):
            if "time=" in line:
                print(f"    {line.strip()}")
    else:
        TroubleshooterData.problems_found.append((f"Cannot ping {SMB_SERVER}", 7))


def check_current_mount() -> None:
    """[8] Check if share is currently mounted"""

    mount_result = run_command(f"mount | grep {MOUNT_POINT}")
    is_mounted = mount_result.returncode == 0

    # print_status(is_mounted, "Share is currently mounted?")
    if not is_mounted:
        TroubleshooterData.problems_found.append(("Share is NOT currently mounted", 8))


def show_journal_logs() -> None:
    """[9] Check recent systemd journal entries"""

    print("--- Mount unit logs (last 5 lines) ---")
    mount_logs = run_command(f"journalctl -u {MOUNT_UNIT_ESCAPED} -n 5 --no-pager 2>&1")
    log_lines = mount_logs.stdout.strip().split("\n")
    for line in log_lines[-5:]:
        print(line)

    print("\n--- Automount unit logs (last 5 lines) ---")
    automount_logs = run_command(f"journalctl -u {AUTOMOUNT_UNIT_ESCAPED} -n 5 --no-pager 2>&1")
    log_lines = automount_logs.stdout.strip().split("\n")
    for line in log_lines[-5:]:
        print(line)


def print_problems() -> None:
    """[10] Print problems found"""

    if TroubleshooterData.problems_found:
        print(f"Troubleshooter discovered {len(TroubleshooterData.problems_found)} problems:")
        for problem in TroubleshooterData.problems_found:
            print(f"Found in step {problem[1]}: {problem[0]}")
