"""
Contains the fstab tab for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations
import subprocess

# from typing import Any  # , cast
# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on, work  # , log
from textual.app import ComposeResult
from textual.widgets import TabPane, Placeholder, Button
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.binding import Binding
from textual.widgets import Static, Switch, TextArea  # , Button, Select

# Local imports
import systemd_mount_manager.logic as logic

# Goals:
# 1) DONE - Add "edit" button to open user's $EDITOR to edit fstab - suspend app
#      using Textual's "suspend" feature
# 2) DONE - Auto-refresh the fstab data after editing
# 3) Parse the fstab entries and display them in a table
# 4) Add coloring / syntax highlighting to the fstab entries
# 5) Find any .mount files generated in /usr/run/system


class FstabsCard(Container):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="h2"):
            yield Static("Your /etc/fstab file:", classes="compact-static")
            yield Container()
            yield Button("Open in Editor", id="edit-button", compact=True)
            yield Button("Refresh", id="refresh-button", compact=True)
        yield TextArea(read_only=True, soft_wrap=False, show_line_numbers=True)

    def on_mount(self) -> None:
        self.get_fstabs()

    def get_fstabs(self) -> None:
        self.log("Reading /etc/fstab")
        with open("/etc/fstab", "r") as f:
            fstab_str = f.read()
        fstab_data = logic.fstab.parse_fstab(fstab_str)
        self.query_one(TextArea).load_text(fstab_str)
        self.log(fstab_data)

    @on(Button.Pressed, "#refresh-button")
    def refresh_button_pressed(self) -> None:
        self.get_fstabs()

    @on(Button.Pressed, "#edit-button")
    @work
    async def edit_button_pressed(self) -> None:
        
        try:
            editor: str = logic.core.get_editor()
        except Exception as e:
            self.log(f"Could not find editor: {e}")
            self.notify("ERROR: Could not find editor")
            return
        with self.app.suspend():
            subprocess.run(['sudo', editor, '/etc/fstab'])
        # refresh after editing:
        self.get_fstabs()
            

class FstabTab(TabPane):

    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            with Container(id="settings-container", classes="card-container"):
                yield FstabsCard(classes="hauto")
