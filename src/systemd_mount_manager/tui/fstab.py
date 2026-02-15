"""
Contains the fstab tab for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations
import subprocess
from enum import Enum
from pathlib import Path

# from typing import Any  # , cast
# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on, work  # , log
import textual.events as events
from textual.app import ComposeResult
from textual.widgets import TabPane, Placeholder, Button
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    VerticalScroll,
    HorizontalScroll,
)
from textual.binding import Binding
from textual.widgets import Static, Switch, TextArea, RichLog  # , Button, Select
from textual.screen import ModalScreen
from textual.content import Content
from rich.text import Text

# Local imports
import systemd_mount_manager.logic as logic
from systemd_mount_manager.tui.screens import SudoWarningScreen, SudoWarningScreenResult

# Goals:
# 1) DONE - Add "edit" button to open user's $EDITOR to edit fstab - suspend app
#      using Textual's "suspend" feature
# 2) DONE - Auto-refresh the fstab data after editing
# 3) Parse the fstab entries and display them in a table
# 4) Add coloring / syntax highlighting to the fstab entries
# 5) Find any .mount files generated in /usr/run/system
# 6) Add warning screen when opening the editor about sudo/privileges


class FstabsCard(Container):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="h2"):
            yield Static("Your /etc/fstab file:", classes="compact-static")
            yield Container()
            yield Button("Open in Editor", id="edit-button", compact=True)
            yield Button("Refresh", id="refresh-button", compact=True)
        yield ScrollableContainer(id="fstab-lines-container")

    def on_mount(self) -> None:
        self.get_fstabs()

    def get_fstabs(self) -> None:
        self.log("Reading /etc/fstab")
        with open("/etc/fstab", "r") as f:
            fstab_str = f.read()
        fstab_data = logic.fstab.parse_fstab(fstab_str)
        fstabs_statics = self.fstab_data_pretty_print(fstab_data)
        fstab_con = self.query_one("#fstab-lines-container")
        fstab_con.mount_all(fstabs_statics)

        # for line in fstab_data_pretty:
        #     fstab_con.mount(Static(line, classes="wauto"))
        fstab_con.scroll_home(animate=False)
        # self.log(fstab_data)

    @on(Button.Pressed, "#refresh-button")
    def refresh_button_pressed(self) -> None:
        self.get_fstabs()

    @on(Button.Pressed, "#edit-button")
    @work
    async def edit_button_pressed(self) -> None:

        warning_mode: bool = logic.config.config.getboolean("DEFAULT", "show_sudo_warning")
        if warning_mode:
            result = await self.app.push_screen_wait(SudoWarningScreen("Editing /etc/fstab"))
            if result == SudoWarningScreenResult.CANCEL:
                return
            elif result == SudoWarningScreenResult.PROCEED_DONT_SHOW_AGAIN:
                logic.config.config.set("DEFAULT", "show_sudo_warning", "False")

        try:
            editor: str = logic.core.get_editor()
        except Exception as e:
            self.log(f"Could not find editor: {e}")
            self.notify("ERROR: Could not find editor")
            return
        with self.app.suspend():
            subprocess.run(["sudo", editor, "/etc/fstab"])
        # refresh after editing:
        self.get_fstabs()

    def fstab_data_pretty_print(self, data: list[logic.fstab.FstabLine]) -> list[Static]:
        """Pretty print the fstab data."""

        # Check type: FstabEntry | FstabComment | FstabInvalid

        pretty_list: list[Static] = []

        for line in data:
            if isinstance(line, logic.fstab.FstabEntry):
                pretty_list.append(
                    Static(
                        Content.from_markup(
                            f"[$success]{line.device.raw}[/] "
                            f"[$accent-darken-1]{line.mount_point}[/] "
                            f"[$primary]{line.fs_type}[/] "
                            f"{line.options.raw} "
                            f"[$warning-darken-1]{line.dump} {line.pass_num}[/]"
                        ),
                        classes="fstab-line",
                    )
                )
            elif isinstance(line, logic.fstab.FstabComment):
                pretty_list.append(
                    Static(
                        Content.from_markup(f"{line.raw_line}"),
                        classes="fstab-line comment",
                    )
                )
            elif isinstance(line, logic.fstab.FstabInvalid):
                pretty_list.append(
                    Static(
                        Content.from_markup(f"{line.raw_line}"),
                        classes="fstab-line invalid",
                    )
                )

        return pretty_list


class FstabTab(TabPane):

    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            yield FstabsCard(classes="card-container")
