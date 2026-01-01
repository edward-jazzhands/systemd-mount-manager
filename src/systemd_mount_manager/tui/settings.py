"""
Contains the Settings tab for Systemd Mount Manager.
"""
# Python imports
from __future__ import annotations
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


class SettingOption(Horizontal):
    def __init__(self, setting_name: str, description: str, value: str) -> None:
        super().__init__()
        self.setting_name = setting_name
        self.description = description
        self.value = value
    
    def compose(self) -> ComposeResult:
        yield Static(self.setting_name, classes="setting-name")
        yield Static(self.description, classes="setting-description")
        yield Static(self.value, classes="setting-value")
        

class SettingsTab(TabPane):
    
    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            with Container(id="settings-container", classes="card-container"):
                yield SettingOption("SMB Server", "The SMB server to connect to", "TrueNAS")
                yield SettingOption("SMB Share", "The SMB share to mount", "brents-data")
                

        
