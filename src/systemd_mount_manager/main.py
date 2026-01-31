from __future__ import annotations
from click import pass_context
import sys
import subprocess
import os

import systemd_mount_manager.logic as logic


try:
    import click
except ImportError:
    print("Warning: click not found. Did you use --system-site-packages?", file=sys.stderr)
    sys.exit(1)


# ANSI color codes
class Color:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;36m"
    GRAY = "\033[1;30m"
    ORANGE = "\033[0;33m"
    NC = "\033[0m"  # No Color


def debug_msg(msg: str, debug: bool) -> None:
    if debug:
        click.echo(msg, err=True)


def is_graphical_session(dev: bool) -> bool:

    # Primary check (most reliable on modern systems)
    if os.environ.get("XDG_SESSION_TYPE") in ("x11", "wayland"):
        debug_msg(f"✓ Graphical session detected: {os.environ.get('XDG_SESSION_TYPE')}", dev)
        return True

    # Fallback for X11 sessions that don't set XDG_SESSION_TYPE
    if "DISPLAY" in os.environ:
        # Optional: quick check that X is actually reachable
        try:
            subprocess.run(
                ["xdpyinfo", "-display", os.environ["DISPLAY"]],
                capture_output=True,
                timeout=2,
                check=True,
            )
            debug_msg("✓ Graphical session detected: X11", dev)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Some Wayland compositors set WAYLAND_DISPLAY
    if "WAYLAND_DISPLAY" in os.environ:
        debug_msg("✓ Graphical session detected: Wayland", dev)
        return True

    debug_msg("No graphical desktop environment detected", dev)
    return False


def check_systemd(dev: bool) -> bool:

    systemd_is_active = False
    systemd_state = ""

    # Check PID 1
    ps_result = subprocess.run(["ps", "-p", "1", "-o", "comm="], capture_output=True, text=True)
    pid1_is_systemd = ps_result.stdout.strip() == "systemd"
    
    # Check systemctl
    try:
        systemctl_result = subprocess.run(
            ["systemctl", "is-system-running"], capture_output=True, text=True
        )
    except:
        pass
    else:
        systemd_state = systemctl_result.stdout.strip()
        systemd_is_active = systemd_state in [
            "running",
            "degraded",
            "starting",
            "stopping",
            "initializing",
            "maintenance",
        ]

    if pid1_is_systemd and systemd_is_active:
        debug_msg("systemd is the init system and running", dev)
        return True
    elif pid1_is_systemd:
        click.echo(
            f"WARNING: systemd is PID 1 but state is: {systemd_state}. "
            "Program may not function correctly."
        )
        return True
    else:
        click.echo(
            f"ERROR: PID 1 is not systemd. Found: {ps_result.stdout.strip()}"
            "\nSystemd Mount Manager requires systemd to be the active OS init system."
        )
        return False


def tui_mode(dev: bool):

    # lazy loading
    from systemd_mount_manager.tui import tui_run

    if dev:
        click.pause("DEV MODE: Press any key to continue")
    tui_run(dev)


# @click.group() creates a command group that can contain subcommands
# @cli.command() registers a subcommand under this group
# Each function gets its own @click.option() decorators
# Flags defined on this group are only available at the top level
# Flags defined on subcommands are only available for those specific subcommands
# If you need to pass context from the parent command to child commands,
# you can use Click's context object with @click.pass_context.


@click.group()
@click.option(
    "--dev",
    is_flag=True,
    default=False,
    help="Development mode - [Warning]: resets config to default",
)
@click.pass_context
def cli(ctx: click.Context, dev: bool) -> None:
    """SystemD Mount Manager - The easiest way to manage network mounts on Linux.
    
    There's 3 ways to use the program: GUI mode, TUI mode, and the CLI.
    Note that systemd is required in order for the program to start."""

    ctx.obj: bool = dev
    debug_msg("DEV MODE is ON", dev)

    sysd_check = check_systemd(dev)
    if sysd_check is False:
        if dev is False:
            raise click.Abort("systemd not detected.")
        else:
            click.echo("Running anyway because dev mode is active...")
    
    # Initialization
    try:
        configwrite_result = logic.config.write_default_config(force=dev)
    except FileExistsError:
        pass
    else:
        if configwrite_result is True:  # means file was created
            debug_msg("New config file was created", dev)
        else:  # file was force overwritten
            debug_msg("Config was overwritten with default values.", dev)


@cli.command()
@click.pass_context
def gui(ctx: click.Context) -> None:
    "Launches the GUI mode"

    gui_available = is_graphical_session(ctx.obj)
    if gui_available:
        from systemd_mount_manager.gui import gui_run

        if ctx.obj:
            click.pause("DEV MODE: Press any key to continue")
        gui_run(ctx.obj)
    else:
        click.echo(
            "Attention: You selected GUI mode, but SystemD Mount Manager could not detect "
            "a graphical desktop. The program will fall back to TUI mode."
        )
        if click.confirm("Continue? [default yes]", default=True, show_default=True):
            tui_mode(ctx.obj)
        else:
            click.echo("Cancelled")
            return


@cli.command()
@click.pass_context
def tui(ctx: click.Context) -> None:
    "Launches the TUI mode"

    tui_mode(ctx.obj)


@cli.command()
def stdio() -> None:
    """stdio mode - read commands from stdin, write responses to stdout.
    This is intended for scripting or interfacing with the app from other programs."""

    logic.core.run_stdio_mode()
    return


def main():
    cli()


if __name__ == "__main__":
    cli()
