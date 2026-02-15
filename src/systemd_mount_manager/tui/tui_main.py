"""
Contains the TUI interface for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations

from typing import Sequence  # , cast
import sys
from dataclasses import dataclass
from pathlib import Path

# Textual imports
from textual import on  # , log
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal

# from textual.widget import Widget
from textual.widgets import TabbedContent
from textual.binding import Binding
from textual.widgets import Footer, Static, ContentSwitcher  # , Button, Select

# from rich.text import Text

# Local imports
import systemd_mount_manager.logic as logic
from systemd_mount_manager.tui.screens import HelpScreen
from systemd_mount_manager.tui.dashboard import DashBoard
from systemd_mount_manager.tui.addmount import AddMountTab
from systemd_mount_manager.tui.mountinfo import MountInfoTab
from systemd_mount_manager.tui.troubleshooter import Troubleshooter
from systemd_mount_manager.tui.settings import SettingsTab
from systemd_mount_manager.tui.fstab import FstabTab


header_ascii = r"""
█▀ █▄█ █▀ ▀█▀ ██▀ █▄░▄█ ▄▄█  █▄░▄█ █▀█ █░█ █▄░█ ▀█▀  █▄░▄█ ▄▀█ █▄░█ ▄▀█ ▄▀░ █▀▀ █▀▄
▄█ ░█░ ▄█ ░█░ █▄▄ █░▀░█ █▄█  █░▀░█ █▄█ █▄█ █░▀█ ░█░  █░▀░█ █▀█ █░▀█ █▀█ ▀▄█ ██▄ █▀▄
"""


class CustomHeader(Container):

    def __init__(self):
        super().__init__()
        # self.app_data = app_data

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(header_ascii.strip(), id="ascii_banner")
            with Container(id="header_info"):
                if self.app._is_devtools_connected:
                    yield Static(f"Dev Mode")


# @dataclass
# class AppData:
#     dev_mode: bool


class TextualApp(App[None]):

    BINDINGS = [
        Binding("f3", "show_help", "Show help"),
        Binding("f4", "log_config_file", "log config file"),
        Binding("f5", "log_DOM_tree", "log DOM tree"),
    ]

    CSS_PATH = "styles.tcss"
    TITLE = "Systemd Mount Manager"

    # def __init__(self) -> None:
    #     super().__init__()
    # self._is_devtools_connected
    # self.app_data = AppData(dev_mode=dev)
    # self.app_data.display = False

    def compose(self) -> ComposeResult:

        # yield self.app_data

        with Container(id="main_container"):
            yield CustomHeader()
            with TabbedContent(id="main_tabs"):
                yield DashBoard("Dashboard")
                yield FstabTab("fstab")
                yield AddMountTab("Add Mount")
                yield MountInfoTab("Mount Info")
                yield Troubleshooter("Troubleshooter")
                yield SettingsTab("Settings", id="settings-tab")
        yield Footer()

    def on_mount(self) -> None:

        self.content_switcher = self.query_one(ContentSwitcher)  # optimize querying

    @on(TabbedContent.TabActivated)
    def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self.log(f"Tab activated: {event.tab.id}")
        if event.tab.id == "--content-tab-settings-tab":
            self.content_switcher.query_one(SettingsTab).load_settings()

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_log_config_file(self) -> None:
        logic.config.textual_log_config_file()

    def action_log_DOM_tree(self) -> None:
        self.log(self.tree)


def tui_run(dev: bool = False) -> None:
    """When `dev` is True, the python process will restart itself using
    the Textual dev-tools package and run this file using Textual dev mode.

    ! Dev option requires UV to be installed.
    """

    if not dev:
        app = TextualApp()
        app.run()
        sys.exit(app.return_code)
    else:
        import os

        script_path = Path(__file__).resolve()
        full_command = ["uv", "run", "textual", "run", "--dev", f"{script_path}"]
        try:
            os.execvp("uv", full_command)
        except OSError as e:
            print(f"ERROR: Failed to execute uv command: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    # When Textual dev-tools runs this file, it'll run tui_run() again with
    # dev bool set to False - but this main guard down here would only be run
    # by the Textual dev-tools. So we're already in dev mode. It's a bit confusing
    # wording, but it's the best I could come up with.
    tui_run(dev=False)
