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
from textual import on  # , log
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widget import Widget
from textual.widgets import TabPane, TabbedContent, Placeholder
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
        Binding("f3", "show_help", "Show help"),
        Binding("f4", "log_config_file", "log config file"),
        Binding("f5", "log_DOM_tree", "log DOM tree"),
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
        self.config_overwritten = False
        if debug:
            config_write_result = logic.write_default_config(force=True)
            # result will be False if config file already existed (overwrite)
            self.config_overwritten = (config_write_result is False)

    def compose(self) -> ComposeResult:
        
        # yield self.app_data

        with Container(id="main_container"):
            yield CustomHeader(app_data=self.app_data)
            with TabbedContent(id="main_tabs"):
                yield DashBoard("Dashboard")
                yield FstabTab("fstab")
                yield AddMountTab("Add Mount")
                yield MountInfoTab("Mount Info")
                yield Troubleshooter("Troubleshooter")
                yield SettingsTab("Settings", id="settings-tab")
        yield Footer()

    def on_mount(self) -> None:

        self.content_switcher = self.query_one(ContentSwitcher) # optimize querying
        self.log("Mount successful")
        if self.config_overwritten:
            self.log("Config file was overwritten with default values")
        else:
            self.log("New config file was generated")

    @on(TabbedContent.TabActivated)
    def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self.log(f"Tab activated: {event.tab.id}") 
        if event.tab.id == "--content-tab-settings-tab":
            self.content_switcher.query_one(SettingsTab).load_settings()

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_log_config_file(self) -> None:
        logic.textual_log_config_file()
        
    def action_log_DOM_tree(self) -> None:
        self.log(self.tree)
        
def tui_run(debug: bool, fallback: bool) -> None:
    app = TextualApp(debug=debug, fallback=fallback)
    app.run()
    sys.exit(app.return_code)
    
    
if __name__ == "__main__":
    # Warning: Running this module will overwrite your config file
    tui_run(debug=True, fallback=False)