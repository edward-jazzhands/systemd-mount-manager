import sys
import subprocess
import os

print("Python paths:")
for path in sys.path:
    print(f"  {path}")

if sys.base_prefix != sys.prefix:
    print("We're in a venv")
else:
    print("We're not in a venv")

try:
    import gi
except ImportError:
    print("Warning: PyGObject not found. Did you use --system-site-packages?")
else:
    print("PyGObject found")
    

def check_systemd():
    """Check if systemd is available and running."""
    # Check if systemctl exists
    try:
        subprocess.run(['systemctl', '--version'], 
                      capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    
    # Check if systemd is the active init system
    return os.path.isdir('/run/systemd/system')

if not check_systemd():
    print("ERROR: systemd is not detected on this system.", file=sys.stderr)
    print("systemd-mount-manager requires systemd to function.", file=sys.stderr)
    sys.exit(1)
else:
    print("systemd is detected and running.")