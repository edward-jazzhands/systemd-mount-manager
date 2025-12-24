#!/usr/bin/env bash

echo "Detecting linux distribution..."

if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "✓ Linux distribution type detected: $ID_LIKE"
    case "$ID_LIKE" in
        *debian*)
            echo "Installing system dependencies..."
            # sudo apt install python3-dev libgirepository1.0-dev \
            # libcairo2-dev pkg-config gir1.2-gtk-4.0 && \
            sudo apt install python3-gi python3-click gir1.2-gtk-4.0 && \
            echo "✓ System dependencies installed successfully"
            ;;
        *fedora*)
            echo "Installing system dependencies..."
            sudo dnf install gtk4 && \
            echo "✓ System dependencies installed successfully"
            ;;
        *)
            echo "Unsupported Linux distribution: $ID_LIKE"
            echo "Sorry! Currently only support Debian-based or Fedora-based."
            exit 1
            ;;
    esac
fi