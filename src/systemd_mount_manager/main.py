from __future__ import annotations
import sys
import subprocess
import os

import systemd_mount_manager.logic as logic

try:
    import click
except ImportError:
    print("Warning: click not found. Did you use --system-site-packages?", file=sys.stderr)
    sys.exit(1)


def debug_msg(msg: str, debug: bool = False) -> None:
    if debug:
        click.echo(msg, err=True)


def gui_mode(debug: bool) -> None:

    from systemd_mount_manager.gui import gui_run

    gui_run(debug)


def tui_mode(debug: bool, fallback: bool = False) -> None:
    """Fallback will be set to True if the user tried --gui mode but they don't
    have a graphical desktop environment available. It's passed into the app so that
    we can give the user a message inside Textual about how the GUI is not available."""

    from systemd_mount_manager.tui import tui_run

    tui_run(debug, fallback)


def stdio_mode() -> None:
    """stdio mode - read commands from stdin, write responses to stdout.
    This is intended for scripting or interfacing with the app from other programs."""

    logic.run_stdio_mode()


def is_graphical_session(debug: bool) -> bool:
    # Primary check (most reliable on modern systems)
    if os.environ.get("XDG_SESSION_TYPE") in ("x11", "wayland"):
        debug_msg(f"✓ Graphical session detected: {os.environ.get('XDG_SESSION_TYPE')}", debug)
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
            debug_msg("✓ Graphical session detected: X11", debug)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Some Wayland compositors set WAYLAND_DISPLAY
    if "WAYLAND_DISPLAY" in os.environ:
        debug_msg("✓ Graphical session detected: Wayland", debug)
        return True

    debug_msg("No graphical desktop environment detected", debug)
    return False


def initialize_app() -> None:

    try:
        logic.write_default_config()
    except FileExistsError:
        debug_msg("Config file already exists, skipping creation", True)


# @click.group() creates a command group that can contain subcommands
# @cli.command() registers a subcommand under this group
# Each function gets its own @click.option() decorators
# Flags defined on this group are only available at the top level
# Flags defined on subcommands are only available for those specific subcommands
# If you need to pass context from the parent command to child commands,
# you can use Click's context object with @click.pass_context.


@click.group()
# @click.argument("path", type=str, default=None, required=False)  here for reference
@click.option("--gui", is_flag=True, default=False, help="Run the GUI version of the application.")
@click.option("--tui", is_flag=True, default=False, help="Run the TUI version of the application.")
@click.option(
    "--stdio",
    is_flag=True,
    default=False,
    help="Run the application in stdio mode (for connecting to UIs / other programs, see docs).",
)
@click.option("--debug", is_flag=True, default=False, help="Run the application in debug mode.")
def cli(gui: bool, tui: bool, stdio: bool, debug: bool) -> None:

    # Very first thing we do: check for systemd
    try:
        subprocess.run(["systemctl", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # These are set to true so they will always show in stderr regardless of debug mode:
        debug_msg("ERROR: systemd is not detected on this system.", True)
        debug_msg("systemd-mount-manager requires systemd to function.", True)
        sys.exit(1)

    # Check if systemd is the active init system
    if not os.path.isdir("/run/systemd/system"):
        debug_msg("ERROR: systemd is installed but NOT running as the init " "system.", True)
        debug_msg(
            "This usually means your system is using a different init " "system (like OpenRC).",
            True,
        )
        debug_msg("systemd-mount-manager requires systemd to be PID 1 to " "manage mounts.", True)
        sys.exit(1)

    debug_msg("✓ systemd is active and running", debug)

    # Once we've established that systemd is active and running, we can proceed
    # with program initialization.
    initialize_app()

    # check if we're running in stdio mode. If so, we can skip the rest
    # of the checks.
    if stdio:
        debug_msg("✓ Running in stdio mode", debug)
        stdio_mode()
        sys.exit(0)

    # Next we have to detect whether there is access to a graphical desktop
    # environment. If there is, we can run the GUI version of the application.
    # Otherwise, we can only run the TUI version.
    if gui and tui:
        debug_msg("Error: You can't pass both --gui and --tui flags. Pick one.", True)
        sys.exit(1)

    debug_msg("Detecting graphical desktop environment...", debug)
    gui_available = is_graphical_session(debug)

    fallback = False
    debug_msg(f"gui_available: {gui_available}", debug)
    if gui and not gui_available:
        gui = False
        tui = True
        fallback = True
        debug_msg(
            "Warning: You've selected to run the GUI version of the application, "
            "but no graphical desktop environment is detected. \n"
            "Falling back to the TUI interface.",
            debug,
        )

    if gui:
        gui_mode(debug)
    elif tui:
        tui_mode(debug)
    else:
        if gui_available:
            click.echo(
                "Detected that you have a graphical desktop environment available. \n"
                "Please choose between GUI mode or TUI mode. "
                "(Hint: Pass through the --gui or --tui flag to force a specific mode.)"
            )
            usr_input = click.prompt(
                "Select mode [gui/tui (g/t)]",
                type=click.Choice(["gui", "g", "tui", "t"], case_sensitive=False),
                show_choices=False,
            )
            if usr_input in ["gui", "g"]:
                debug_msg("Launching in GUI mode.", debug)
                gui_mode(debug)
            elif usr_input in ["tui", "t"]:
                debug_msg("Launching in TUI mode.", debug)
                tui_mode(debug)
        else:
            click.echo("No graphical desktop environment detected. Launching in TUI mode.")
            tui_mode(debug, fallback)


@cli.command()
@click.option("--flag3", is_flag=True, help="Nested command flag 3")
@click.option("--flag4", is_flag=True, help="Nested command flag 4")
def nested_command(flag3: bool, flag4: bool) -> None:
    """A nested command with its own flags."""

    if flag3:
        click.echo("Flag3 is set")
    if flag4:
        click.echo("Flag4 is set")


def main():
    cli()


if __name__ == "__main__":
    cli()
