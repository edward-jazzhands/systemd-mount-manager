"""
Contains the TUI interface for Systemd Mount Manager.
"""

# ~ Type Checking (Pyright and MyPy) - Strict Mode
# ~ Linting - Ruff
# ~ Formatting - Black - max 100 characters / line

# Python imports
from __future__ import annotations
from typing import Any  # , cast
import sys
from dataclasses import dataclass

# Textual imports
# from textual import on  # , log
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widget import Widget
from textual.widgets import TabPane, TabbedContent, Placeholder
from textual.binding import Binding
from textual.widgets import Footer, Static, Switch  # , Button, Select
# from rich.text import Text

# Local imports
from systemd_mount_manager.tui.screens import HelpScreen
from systemd_mount_manager.tui.dashboard import DashBoard
from systemd_mount_manager.tui.addmount import AddMountTab
from systemd_mount_manager.tui.mountinfo import MountInfoTab
from systemd_mount_manager.tui.troubleshooter import Troubleshooter
from systemd_mount_manager.tui.settings import SettingsTab



header_ascii = r"""
|  | |==   /\   |=\  |== |= \ 
|--| |--  /__\  |- | |-- |_ /
|  | |__ /    \ |-/  |__ |  \
"""

class CustomHeader(Container):
    
    def __init__(self, app_data: AppData):
        super().__init__()
        self.app_data = app_data
    
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(header_ascii.strip(), id="ascii_banner")
            with Container(id="header_info"):
                yield Static(f"Dev Mode: {self.app_data.dev_mode}")
                yield Static(f"Fallback: {self.app_data.fallback}")
        
        
    
@dataclass                
class AppData:
    dev_mode: bool
    fallback: bool
    

class TextualApp(App[None]):

    BINDINGS = [
        Binding("f1", "show_help", "Show help"),
    ]

    CSS_PATH = "styles.tcss"
    TITLE = "Systemd Mount Manager"

    def __init__(self, debug: bool, fallback: bool) -> None:
        super().__init__()
        self.app_data = AppData(
            dev_mode=debug,
            fallback=fallback
        )
        # self.app_data.display = False

    def compose(self) -> ComposeResult:
        
        # yield self.app_data

        with Container(id="main_container"):
            yield CustomHeader(app_data=self.app_data)
            with TabbedContent(id="main_tabs"):
                yield DashBoard("Dashboard")
                yield Troubleshooter("Troubleshooter")
                yield AddMountTab("Add Mount")
                yield MountInfoTab("Mount Info")
                yield SettingsTab("Settings")
        yield Footer()

    def on_mount(self) -> None:

        self.log("Mount successful")

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

        
def tui_run(debug: bool, fallback: bool) -> None:
    app = TextualApp(debug=debug, fallback=fallback)
    app.run()
    sys.exit(app.return_code)
    
    
if __name__ == "__main__":
    tui_run(debug=True, fallback=False)