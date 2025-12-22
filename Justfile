# Setup development environment
setup-traditional:
    #!/usr/bin/env bash
    python3 -m venv --system-site-packages venv
    ./venv/bin/pip install -e .
    echo "✓ Setup complete! Run 'just run' to start"
    
setup-uv:
    #!/usr/bin/env bash
    uv venv --python-preference only-system --system-site-packages
    uv sync

install-deps:
    #!/usr/bin/env bash
    echo "Detecting linux distribution..."
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "✓ Linux distribution detected: $ID"
        case "$ID" in
            "debian")
                echo "Installing system dependencies..."
                sudo apt install polkit-1, python3-gi, gir1.2-gtk-4.0 && \
                echo "✓ System dependencies installed successfully"
                ;;
            "fedora")
                echo "Installing system dependencies..."
                sudo dnf install polkit, python3-gobject, gtk4 && \
                echo "✓ System dependencies installed successfully"
                ;;
            *)
                echo "Unsupported Linux distribution: $ID"
                exit 1
                ;;
        esac
    echo "✓ System dependencies installed successfully"

    # For `.deb`:
    # Depends: polkit-1, python3-gi, gir1.2-gtk-4.0
    # For `.rpm`:
    # Requires: polkit, python3-gobject, gtk4

# Run the application
run:
    .venv/bin/python3 src/net_mount_2025/gitest.py

# Clean up
nuke:
    rm -rf venv