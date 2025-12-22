from __future__ import annotations
import sys
import subprocess
import os
from importlib.util import find_spec

# Very first thing we do: check for systemd
try:
    subprocess.run(['systemctl', '--version'], 
                    capture_output=True, check=True)
except (subprocess.CalledProcessError, FileNotFoundError):
    print("ERROR: systemd is not detected on this system.", file=sys.stderr)
    print("systemd-mount-manager requires systemd to function.", file=sys.stderr)
    sys.exit(1)

# Check if systemd is the active init system
if not os.path.isdir('/run/systemd/system'):
    print(
        "ERROR: systemd is installed but NOT running as the init "
        "system.", file=sys.stderr
    )
    print(
        "This usually means your system is using a different init "
        "system (like OpenRC).", file=sys.stderr
    )
    print(
        "systemd-mount-manager requires systemd to be PID 1 to "
        "manage mounts.", file=sys.stderr
    )
    sys.exit(1)

print("✓ systemd is active and running", file=sys.stderr)

# if sys.base_prefix != sys.prefix:  # We're in a venv
# NOTE: I believe the above check is not logically necessary.
# We can just do the safe check for `gi` regardless of whether we're
# doing local dev or running as a system app.
if not find_spec("gi"):
    print("Warning: PyGObject not found. Did you use --system-site-packages?", file=sys.stderr)
    sys.exit(1)

# This is down here so we don't try to load it unless we're sure that
# the system is running systemd.
import gi  # noqa: E402

try:
    gi.require_version('Gtk', '3.0')  # or '4.0' depending on target
    from gi.repository import Gtk
except (ValueError, ImportError) as e:
    print(f"ERROR: GTK not available: {e}", file=sys.stderr)
    sys.exit(1)