from __future__ import annotations
from importlib.util import find_spec
import sys

# if sys.base_prefix != sys.prefix:  # We're in a venv
# NOTE: I believe the above check is not logically necessary.
# We can just do the safe check for `gi` regardless of the venv.
if not find_spec("gi"):
    print("Warning: PyGObject not found. Did you use --system-site-packages?")
    sys.exit(1)

import gi
from typing import Sequence
import subprocess
from pathlib import Path

# ANSI color codes
class Color:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;36m"
    GRAY = "\033[1;30m"
    NC = "\033[0m"  # No Color


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
SCRIPT_DIR: Path = Path(__file__).parent.resolve()
HOME: Path = Path.home()


def get_input(prompt: str, options: str, default: str) -> str:
    """
    Helper to handle interactive prompts with validation.
    - If user enters an invalid option, they will be prompted again.
    - If user enters a blank option, the default will be returned.
    """

    while True:
        try:
            user_input: str = (
                input(
                    f"{Color.BLUE}{prompt}{Color.NC}\n({options} [default={default}]): "
                )
                .lower()
                .strip()
            )
            if not user_input:
                return default
            # Check if input matches any character in the options string (ignoring separators)
            valid_chars: str = options.lower().replace("/", "")
            if user_input in valid_chars and len(user_input) == 1:
                return user_input
            print(
                f"{Color.RED}Invalid input. Please enter one of: {options}.{Color.NC}"
            )
        except EOFError:
            return default


class Setup:
    def __init__(self, display_output: bool = False, dry_run: bool = False) -> None:
        self.problems_found: list[tuple[str, int]] = []
        self.display_output: bool = display_output
        self.dry_run: bool = dry_run

    def run_command(self, cmd: Sequence[str], use_sudo: bool = False) -> None:
        """Runs a shell command or simulates it if self.dry_run is True."""

        full_cmd: list[str] = (["sudo"] + list(cmd)) if use_sudo else list(cmd)
        cmd_str: str = " ".join(full_cmd)

        if self.dry_run:
            print(f"{Color.YELLOW}[DRY-RUN]{Color.NC} Would execute: {cmd_str}")
            return

        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                full_cmd, capture_output=True, text=True, check=False
            )
            # return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            print(f"{Color.RED}Error{Color.NC}: {e}")
        else:
            print(f"{Color.GREEN}Success{Color.NC}: {result.stdout + result.stderr}")

    def create_symlink(self, source: Path, target: Path) -> None:
        """Creates a symbolic link, or simulates it if dry_run is True."""
        target_path: Path = target.expanduser()

        if self.dry_run:
            print(
                f"{Color.YELLOW}[DRY-RUN]{Color.NC} Would symlink: {source} -> {target_path}"
            )
            return

        try:
            if target_path.exists() or target_path.is_symlink():
                target_path.unlink()
            target_path.symlink_to(source)
        except Exception as e:
            print(f"{Color.RED}Error creating symlink for {target_path}: {e}{Color.NC}")
        else:
            print(f"{Color.GREEN}Success:{Color.NC} {source} -> {target_path}")

    def symlink_dotfiles(self) -> None:
        """Symlink dotfiles"""

        dotfiles: list[str] = [
            ".bashrc",
            ".gitconfig",
            ".gitignore_global",
            ".justfile",
            ".tmux.conf",
        ]
        for f in dotfiles:
            source = SCRIPT_DIR / f
            target = HOME / f
            self.create_symlink(source, target)

    def setup_truenas_smb(self) -> None:
        """Symlink TrueNAS SMB shares"""

        mount_type: str = get_input(
            "Mount at boot (b), or mount lazily/automount (l)?", "b/l", "l"
        )

        if mount_type == "b":
            print("Attempting to disable automount if enabled")
            self.run_command(["systemctl", "disable", AUTOMOUNT_UNIT], use_sudo=True)

            print("Creating symlink for mount at boot")
            src_mount: Path = SCRIPT_DIR / "systemd" / MOUNT_UNIT
            self.run_command(
                ["ln", "-sf", str(src_mount), str(SYSTEMD_PATH)],
                use_sudo=True,
            )

            print("Enabling mount at boot in systemctl")
            self.run_command(["systemctl", "enable", MOUNT_UNIT], use_sudo=True)

        else:  # Lazy/Automount
            print("Attempting to disable mount at boot if enabled")
            self.run_command(["systemctl", "disable", MOUNT_UNIT], use_sudo=True)

            print("Creating both symlinks (Both are required)")
            for unit in [MOUNT_UNIT, AUTOMOUNT_UNIT]:
                src_unit: Path = SCRIPT_DIR / "systemd" / unit
                self.run_command(
                    ["ln", "-sf", str(src_unit), str(SYSTEMD_PATH)],
                    use_sudo=True,
                )

            print("Enabling only automount in systemctl")
            self.run_command(["systemctl", "enable", AUTOMOUNT_UNIT], use_sudo=True)

        print("\nConfiguration complete.")


class Troubleshooter:
    def __init__(self, display_output: bool = False) -> None:
        self.problems_found: list[tuple[str, int]] = []
        self.display_output: bool = display_output
        self.automount_path_exists: bool

    def start(self) -> None:
        self.check_unit_files()
        self.check_enabled_units()
        self.show_systemctl_dashboard()
        self.check_tailscale()
        self.check_mount_point()
        self.check_credentials()
        self.check_network()
        self.check_current_mount()
        self.show_journal_logs()
        self.print_problems()

    def print_status(self, success: bool, message: str) -> None:
        """Print a status message with checkmark or X"""
        symbol = (
            f"[{Color.GREEN}✓{Color.NC}]" if success else f"[{Color.RED}X{Color.NC}]"
        )
        print(f"{symbol} {message}")

    def run_command(
        self, cmd: str, display_output: bool = False, check: bool = True
    ) -> subprocess.CompletedProcess[str] | subprocess.CalledProcessError:
        """Run a shell command and return result"""
        if self.display_output:
            display_output = True
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, check=check
            )
        except subprocess.CalledProcessError as e:
            return e
        else:
            if display_output:
                if result.stdout:
                    print(
                        f"{Color.YELLOW}Command output:{Color.GRAY} {result.stdout.strip()}{Color.NC}"
                    )
                elif result.stderr:
                    print(
                        f"{Color.RED}Command error:{Color.GRAY} {result.stderr.strip()}{Color.NC}"
                    )
                else:
                    print(
                        f"{Color.RED}Command output:{Color.GRAY} no output to display{Color.NC}"
                    )
            return result

    def check_unit_files(self) -> None:
        """[1] Check if systemd unit files exist"""
        print(f"{Color.BLUE}[1] Checking systemd unit files...{Color.NC}")

        mount_path = Path(f"/etc/systemd/system/{MOUNT_UNIT}")
        automount_path = Path(f"/etc/systemd/system/{AUTOMOUNT_UNIT}")

        self.print_status(mount_path.exists(), "Mount unit file exists?")
        if not mount_path.exists():
            print("    Mount unit NOT found in /etc/systemd/system/")
            self.problems_found.append(
                ("Mount unit file NOT found in /etc/systemd/system/", 1)
            )

        self.print_status(automount_path.exists(), "Automount unit file exists?")
        if not automount_path.exists():
            print("    Automount unit not found (this is OK if mounting at boot)")
            self.automount_path_exists = False
        else:
            self.automount_path_exists = True

    def check_enabled_units(self) -> None:
        """[2] Check which units are enabled"""
        print(
            f"\n{Color.BLUE}[2] Checking enabled units... (Only 1 must be enabled){Color.NC}"
        )

        is_one_enabled = False

        # Mount at boot
        mount_enabled_result = self.run_command(
            f"systemctl is-enabled {MOUNT_UNIT_ESCAPED}"
        )
        mount_enabled = mount_enabled_result.returncode == 0
        self.print_status(mount_enabled, "Mount at boot unit enabled?")
        if mount_enabled:
            is_one_enabled = True

        # Automount
        automount_enabled_result = self.run_command(
            f"systemctl is-enabled {AUTOMOUNT_UNIT_ESCAPED}"
        )
        automount_enabled = automount_enabled_result.returncode == 0
        self.print_status(automount_enabled, "Auto-mount at boot unit enabled?")
        if automount_enabled:
            is_one_enabled = True
            if not self.automount_path_exists:
                print(
                    f"{Color.YELLOW}    WARNING: Automount unit is enabled, "
                    f"but automount path does NOT exist.{Color.NC}"
                )
                self.problems_found.append(
                    ("Automount unit is enabled, but automount path does NOT exist", 2)
                )

        if not is_one_enabled:
            self.problems_found.append(
                ("Neither automount nor mount at boot unit is enabled in systemctl", 2)
            )

    def show_systemctl_dashboard(self) -> None:
        """[3] Display the systemctl status dashboard for the mounts."""

        print(f"\n{Color.BLUE}[3] Displaying systemctl status dashboards...{Color.NC}")

        print(f"{Color.YELLOW}--- Mount status ---{Color.NC}")
        mount_status_result = self.run_command(
            f"systemctl status {MOUNT_UNIT_ESCAPED} --no-pager 2>&1",
        )
        print("\n".join(mount_status_result.stdout.split("\n")[:5]))

        print(f"\n{Color.YELLOW}--- Automount status ---{Color.NC}")
        automount_status_result = self.run_command(
            f"systemctl status {AUTOMOUNT_UNIT_ESCAPED} --no-pager 2>&1",
        )
        print("\n".join(automount_status_result.stdout.split("\n")[:5]))

    def check_tailscale(self) -> None:
        """[4] Check Tailscale status"""
        print(f"\n{Color.BLUE}[4] Checking Tailscale...{Color.NC}")

        # First check if tailscale command exists and is connected
        tailscale_installed_result = self.run_command("command -v tailscale")
        tailscale_installed = tailscale_installed_result.returncode == 0
        self.print_status(tailscale_installed, "Tailscale installed?")
        if not tailscale_installed:
            print(
                f"{Color.YELLOW}    Tailscale command NOT found. "
                f"Do you have Tailscale installed?{Color.NC}"
            )
            self.problems_found.append(
                ("Tailscale command NOT found. Do you have Tailscale installed?", 4)
            )
            return

        # Tailscale is installed, check if running:
        tailscaled_active_result = self.run_command(
            "systemctl is-active tailscaled.service"
        )
        tailscaled_active = tailscaled_active_result.returncode == 0
        self.print_status(tailscaled_active, "Is Tailscaled running?")
        if not tailscaled_active:
            print(f"{Color.YELLOW}    Tailscaled is NOT running{Color.NC}")
            self.problems_found.append(("Tailscaled is NOT running", 4))
            return

        # Tailscale is running, check if connected:
        tailscale_status = self.run_command("tailscale status 2>&1")
        is_connected = tailscale_status.returncode == 0
        self.print_status(is_connected, "Tailscale is connected?")
        if not is_connected:
            print(f"{Color.YELLOW}    Tailscale is NOT connected{Color.NC}")
            self.problems_found.append(("Tailscale is NOT connected", 4))
            return

    def check_mount_point(self) -> None:
        """[5] Check if mount point directory exists"""
        print(f"\n{Color.BLUE}[5] Checking mount point directory...{Color.NC}")

        mount_path = Path(MOUNT_POINT)
        exists = mount_path.exists() and mount_path.is_dir()

        self.print_status(exists, f"Mount point directory exists?: {MOUNT_POINT}")
        if not exists:
            print(f"{Color.YELLOW}    Run: sudo mkdir -p {MOUNT_POINT}{Color.NC}")
            self.problems_found.append(
                (f"Mount point directory does NOT exist: {MOUNT_POINT}", 5)
            )

    def check_credentials(self) -> None:
        """[6] Check credentials file"""
        print(f"\n{Color.BLUE}[6] Checking credentials file...{Color.NC}")

        creds_path = Path(CREDS_FILE)
        exists = creds_path.exists()

        self.print_status(exists, f"Credentials file exists?: {CREDS_FILE}")
        if exists:
            # Check permissions
            stat_result = self.run_command(f"stat -c %a {CREDS_FILE}")
            perms = stat_result.stdout.strip()

            is_secure = perms in ["600", "400"]
            self.print_status(is_secure, f"Permissions are secure?: {perms}")
            if not is_secure:
                print(
                    f"{Color.YELLOW}    Permissions may be too open: {perms} (should be 600 or 400)"
                )
                print(f"    Run: sudo chmod 600 {CREDS_FILE}{Color.NC}")
                self.problems_found.append(
                    (f"Permissions may be too open: {perms} (should be 600 or 400)", 6)
                )
        else:
            print(f"{Color.RED}    Credentials file NOT found{Color.NC}")
            self.problems_found.append(("Credentials file NOT found", 6))

    def check_network(self) -> None:
        """[7] Check network connectivity to TrueNAS"""
        print(f"\n{Color.BLUE}[7] Checking network connectivity...{Color.NC}")

        ping_result = self.run_command(f"ping -c 1 -W 2 {SMB_SERVER} 2>&1")
        can_ping = ping_result.returncode == 0

        self.print_status(can_ping, f"Can ping {SMB_SERVER}?")
        if can_ping:
            print(
                f"    {Color.GREEN}Confirmed can ping {SMB_SERVER}, results:{Color.NC}"
            )
            # Extract time from ping output
            for line in ping_result.stdout.split("\n"):
                if "time=" in line:
                    print(f"    {line.strip()}")
        else:
            print(f"{Color.YELLOW}    Check Tailscale connection and DNS{Color.NC}")
            self.problems_found.append((f"Cannot ping {SMB_SERVER}", 7))

    def check_current_mount(self) -> None:
        """[8] Check if share is currently mounted"""
        print(f"\n{Color.BLUE}[8] Checking current mount status...{Color.NC}")

        mount_result = self.run_command(f"mount | grep {MOUNT_POINT}")
        is_mounted = mount_result.returncode == 0

        self.print_status(is_mounted, "Share is currently mounted?")
        if not is_mounted:
            print(f"    {Color.RED}Share is NOT currently mounted{Color.NC}")
            print(
                f"{Color.YELLOW}    Run: sudo mount -t cifs //"
                f"{SMB_SERVER}/{SMB_SHARE} {MOUNT_POINT} -o credentials={CREDS_FILE},"
                f"vers=3.0,uid=1000,gid=1000{Color.NC}"
            )
            self.problems_found.append(("Share is NOT currently mounted", 8))

    def show_journal_logs(self) -> None:
        """[9] Check recent systemd journal entries"""
        print(f"\n{Color.BLUE}[9] Recent systemd journal entries...{Color.NC}")

        print("--- Mount unit logs (last 5 lines) ---")
        mount_logs = self.run_command(
            f"journalctl -u {MOUNT_UNIT_ESCAPED} -n 5 --no-pager 2>&1"
        )
        log_lines = mount_logs.stdout.strip().split("\n")
        for line in log_lines[-5:]:
            print(line)

        print("\n--- Automount unit logs (last 5 lines) ---")
        automount_logs = self.run_command(
            f"journalctl -u {AUTOMOUNT_UNIT_ESCAPED} -n 5 --no-pager 2>&1"
        )
        log_lines = automount_logs.stdout.strip().split("\n")
        for line in log_lines[-5:]:
            print(line)

    def print_problems(self) -> None:
        """[10] Print problems found"""

        if self.problems_found:
            print(f"\n{Color.YELLOW}=== Problems Found ==={Color.NC}\n")
            print(f"Troubleshooter discovered {len(self.problems_found)} problems:")
            for problem in self.problems_found:
                print(f"Found in step {problem[1]}: {problem[0]}")
        else:
            print(f"\n{Color.GREEN}=== No Problems Found ==={Color.NC}\n")


################################################################################


def main() -> None:
    """Main function"""

    print("Choose which program to run:")
    print("    1. Dotfile Symlink Creator")
    print("    2. SMB Over Tailscale Setup")
    print("    3. SMB Over Tailscale Troubleshooter")

    user_input = get_input("Enter a number: ", "1/2/3", "1")

    if user_input == "1":
        print("#=============================================#")
        print("              Dotfiles Symlinker")

        # Interactive Dry-Run Prompt
        dry_run_choice: str = get_input(
            "Run in Dry-Run mode? (No changes will be made)", "y/n", "n"
        )
        dry_run: bool = dry_run_choice == "y"
        if dry_run:
            print(
                f"{Color.YELLOW}>>> DRY-RUN MODE ACTIVE: "
                f"No changes will be written to disk. <<<{Color.NC}\n"
            )
        else:
            print(
                f"{Color.RED}WARNING: Symlinks will overwrite existing "
                f".bashrc and other files.{Color.NC}\n"
            )

        setup = Setup(dry_run=dry_run)
        setup.symlink_dotfiles()

    elif user_input == "2":
        print("#=============================================#")
        print("            SMB Over Tailscale Setup")
        
        # Interactive Dry-Run Prompt
        dry_run_choice: str = get_input(
            "Run in Dry-Run mode? (No changes will be made)", "y/n", "n"
        )
        dry_run: bool = dry_run_choice == "y"
        if dry_run:
            print(
                f"{Color.YELLOW}>>> DRY-RUN MODE ACTIVE: "
                f"No changes will be written to disk. <<<{Color.NC}\n"
            )
        setup = Setup(dry_run=dry_run)
        setup.setup_truenas_smb()
        
    elif user_input == "3":
        
        print("#==============================================#")
        print("      SMB Over Tailscale Troubleshooter")
        
        print(
            "Display full command output? (Helpful for debugging) (y/n[default]): "
        )
        user_input = input().lower().strip()
        if user_input == "y":
            display_output = True
        else:
            display_output = False
        Troubleshooter(display_output=display_output).start()


################################################################################


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}Interrupted by user{Color.NC}")
        sys.exit(0)
    except Exception as e:
        print(f"{Color.RED}Error: {e}{Color.NC}", file=sys.stderr)
        sys.exit(1)
