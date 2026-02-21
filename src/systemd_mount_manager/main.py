from __future__ import annotations
from typing import Any
from cgi import FieldStorage
from click import pass_context
import sys
import subprocess
import os

# third party libs
import click

# local imports
import systemd_mount_manager.logic as logic

DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50


# ANSI color codes
class Color:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;36m"
    GRAY = "\033[1;30m"
    ORANGE = "\033[0;33m"
    NC = "\033[0m"  # No Color


def log(level: int, msg: str, dev: bool) -> None:
    if dev:
        click.echo(msg, err=True)
    logic.logger.log(level=level, msg=msg)


def is_graphical_session(dev: bool) -> bool:
    """This is run only by the gui_mode function, to determine if its possible
    for the GUI mode to be used."""

    # Primary check (most reliable on modern systems)
    if os.environ.get("XDG_SESSION_TYPE") in ("x11", "wayland"):
        log(DEBUG, f"✓ Graphical session detected: {os.environ.get('XDG_SESSION_TYPE')}", dev)
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
            log(DEBUG, "✓ Graphical session detected: X11", dev)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Some Wayland compositors set WAYLAND_DISPLAY
    if "WAYLAND_DISPLAY" in os.environ:
        log(DEBUG, "✓ Graphical session detected: Wayland", dev)
        return True

    log(DEBUG, "No graphical desktop environment detected", dev)
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
        log(DEBUG, f"systemd state: {systemd_state}", dev)
        return True
    elif pid1_is_systemd:
        log(WARNING, 
            f"WARNING: systemd is PID 1 but state is: {systemd_state}. "
            "Program may not function correctly.",
            True,   # always print to console regardless of dev mode
        )
        return True
    else:
        log(ERROR, 
            f"ERROR: PID 1 is not systemd. Found: {ps_result.stdout.strip()}"
            "\nSystemd Mount Manager requires systemd to be the active OS init system.",
            True,   # always print to console regardless of dev mode
        )
        return False


def gui_mode(context: logic.core.StartupResult) -> None:

    gui_available = is_graphical_session(context.dev)
    if gui_available:
        from systemd_mount_manager.gui import gui_run

        if context.dev:
            click.pause("DEV MODE: Press any key to continue")
        gui_run(context)
    else:
        click.echo(
            "Attention: You selected GUI mode, but systemd Mount Manager could not detect "
            "a graphical desktop. The program will fall back to TUI mode."
        )
        if click.confirm("Continue? [default yes]", default=True, show_default=True):
            tui_mode(context)
        else:
            click.echo("Cancelled")
            return


def tui_mode(context: logic.core.StartupResult) -> None:

    # lazy loading
    from systemd_mount_manager.tui import tui_run

    if context.dev:
        click.echo(f"Number of errors: {len(logic.core.error_storage)}")
        click.pause("DEV MODE: Press any key to continue")
    tui_run(context)


# @click.group() creates a command group that can contain subcommands
# @cli.command() registers a subcommand under this group
# Each function gets its own @click.option() decorators
# Flags defined on this group are only available at the top level
# Flags defined on subcommands are only available for those specific subcommands
# If you need to pass context from the parent command to child commands,
# you can use Click's context object with @click.pass_context.


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """systemd Mount Manager - The easiest way to manage network mounts on Linux.

    There's 2 ways to use the program: TUI mode, and the CLI.
    Note that systemd is required in order for the program to start."""

    dev = logic.core.check_dev_env_var()
    log(DEBUG, f"Dev mode: {dev}", dev)

    # Initialization
    # If any exceptions were raised during the initialization process,
    # they'll be sent to the error storage in the core module, which will
    # log them as they come in. So we don't need to log those exceptions here.
    # Here we just log the final result (booleans) as debug messages.

    startup_logging_result: bool = logic.log_setup.startup_logging()
    log(DEBUG, f"Logging startup result: {startup_logging_result}", dev)
    # This will return True if the file handler was initialized successfully,
    # or false if the file handler failed to initialize.
    # We can continue but we will want to alert the user when the program starts.
    # There will be other logging handlers that should be essentially guaranteed
    # to be initialized.

    sysd_check = check_systemd(dev)
    if sysd_check is False:
        if dev is False:
            raise click.Abort("systemd not detected.")
        else:
            click.echo("Running anyway because dev mode is active...")

    startup_config_result: bool = logic.config.startup_config()
    log(DEBUG, f"Config startup result: {startup_config_result}", dev)
    # True means either we successfully created a new config file, or we
    # were able to read an existing config file.

    # False means we couldn't create a new config file, or we couldn't read
    # an existing one. The program will fall back to the default config.
    # We can continue but we will want to alert the user

    # Once we've confirmed the config startup has been attempted,
    # we can swap out the memory handler for the file handler.
    file_handler_result: bool = logic.log_setup.add_file_handler_to_logger()
    log(DEBUG, f"File handler startup result: {file_handler_result}", dev)

    startup_results = logic.core.StartupResult(
        logging=startup_logging_result,
        config=startup_config_result,
        handler_swap=file_handler_result,
        dev=dev,
    )
    ctx.obj = startup_results


@cli.command()
@click.pass_obj
def gui(obj: logic.core.StartupResult) -> None:
    "Launches the GUI mode"

    gui_mode(obj)


@cli.command()
@click.pass_obj
def tui(obj: logic.core.StartupResult) -> None:
    "Launches the TUI mode"

    tui_mode(obj)


@cli.command()
def stdio() -> None:
    """stdio mode - read commands from stdin, write responses to stdout.
    This is intended for scripting or interfacing with the app from other programs."""

    logic.core.run_stdio_mode()
    return


def main():

    try:
        cli()
    except Exception as e:

        if dev_mode_env := os.environ.get("SMM_DEV_MODE"):
            if dev_mode_env.lower() in ("1", "true", "yes", "on"):
                raise e
        else:
            click.echo(f"ERROR - Unexpected internal error. See logs for details.")
            sys.exit(1)


if __name__ == "__main__":
    main()
