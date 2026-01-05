from __future__ import annotations
import sys
import click


def debug_msg(msg: str, debug: bool = False) -> None:
    if debug:
        click.echo(msg, err=True)


def gui_run(debug: bool) -> None:
    # if sys.base_prefix != sys.prefix:  # We're in a venv
    # NOTE: I believe the above check is not logically necessary
    # We can just do the safe check for `gi` regardless of whether we're
    # doing local dev or running as a system app.

    # if not find_spec("gi"):
    #     print("Warning: PyGObject not found. Did you use --system-site-packages?", file=sys.stderr)
    #     sys.exit(1)

    # This is down here so we don't try to load it unless we're sure that
    # the system is running systemd.
    try:
        import gi  # noqa: E402
    except (ValueError, ImportError):
        debug_msg("Warning: PyGObject not found. Did you use --system-site-packages?", debug)
        sys.exit(1)

    try:
        gi.require_version("Gtk", "4.0")  # or '3.0' depending on target
        from gi.repository import Gtk
    except (ValueError, ImportError) as e:
        debug_msg(f"ERROR: GTK not available: {e}", debug)
        sys.exit(1)

    debug_msg("GTK and Pygobject were both imported successfully.", debug)
