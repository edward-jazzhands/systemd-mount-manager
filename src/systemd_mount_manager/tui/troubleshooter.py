"""
Contains the troubleshooter for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations

# import subprocess
# from pathlib import Path
# from dataclasses import dataclass
# from typing import Any  # , cast
# import sys
# from dataclasses import dataclass

# Textual imports
# from textual import on  # , log
from textual.app import ComposeResult
from textual.widgets import TabPane, Placeholder
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.binding import Binding
from textual.widgets import Static, Switch  # , Button, Select


# [1] Check if systemd unit files exist
# [2] Check which units are enabled
# [3] Display the systemctl status dashboard for the mounts.
# [4] Check Tailscale status
# [5] Check if mount point directory exists
# [6] Check credentials file
# [7] Check network connectivity to TrueNAS
# [8] Check if share is currently mounted
# [9] Check recent systemd journal entries
# [10] Print problems found


class Troubleshooter(TabPane):

    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            yield Container(classes="card-container center-middle")
