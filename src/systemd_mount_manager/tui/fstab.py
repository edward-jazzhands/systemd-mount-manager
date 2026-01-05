"""
Contains the fstab tab for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations

# from typing import Any  # , cast
# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on  # , log
from textual.app import ComposeResult
from textual.widgets import TabPane, Placeholder, Button
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.binding import Binding
from textual.widgets import Static, Switch, TextArea  # , Button, Select


class FstabsCard(Container):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="h2"):
            yield Static("Your /etc/fstab file:", classes="compact-static")
            yield Container()
            yield Button("Refresh", id="refresh-button", compact=True)
        yield TextArea()

    def on_mount(self) -> None:
        self.get_fstabs()

    def get_fstabs(self) -> None:
        with open("/etc/fstab", "r") as f:
            fstab_str = f.read()
        self.query_one(TextArea).load_text(fstab_str)

    @on(Button.Pressed, "#refresh-button")
    def refresh_button_pressed(self) -> None:
        self.get_fstabs()


class FstabTab(TabPane):

    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            with Container(id="settings-container", classes="card-container"):
                yield FstabsCard(classes="hauto")
