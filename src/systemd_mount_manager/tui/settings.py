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
from textual.binding import Binding
from textual.widgets import Static, Switch  # , Button, Select



        

class SettingsTab(TabPane):
    
    def compose(self) -> ComposeResult:
        yield Placeholder("Settings placeholder")