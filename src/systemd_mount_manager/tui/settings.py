"""
Contains the Settings tab for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations
from enum import Enum
# from typing import Any  # , cast
# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on  # , log
from textual.app import ComposeResult
from textual.widgets import TabPane, Button
from textual.containers import Container, Horizontal, ScrollableContainer
# from textual.binding import Binding
from textual.widgets import Static, Switch, Input  # , Button, Select

import systemd_mount_manager.logic as logic

class SettingType(Enum):
    INPUT = 1
    SWITCH = 2


class SettingOption(Container):
    def __init__(
        self,
        widget_id: str,
        description: str,
        setting_type: SettingType,
        value_str: str | None = None,
        value_bool: bool = False,
    ) -> None:
        super().__init__()
        self.widget_id = widget_id
        self.description = description
        self.value_str = value_str
        self.value_bool = value_bool
        self.setting_type = setting_type

    def compose(self) -> ComposeResult:
        with Horizontal(classes="setting-option-header"):
            yield Static(self.description, classes="setting-description")
            if self.setting_type == SettingType.SWITCH:
                yield Container()
                yield Switch(id=self.widget_id)
                self.add_class("h3")
        if self.setting_type == SettingType.INPUT:
            yield Input(self.value_str, id=self.widget_id)
            self.add_class("h6")
            
    # @on(Input.Submitted, "#setting-input")
    # def input_submitted(self, event: Input.Submitted) -> None:
    #     self.value_str = event.value

    # @on(Switch.Changed, "#setting-switch")
    # def switch_changed(self, event: Switch.Changed) -> None:
    #     self.value_bool = event.value


class SettingsTab(TabPane):
    
    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            with Container(id="settings-container", classes="card-container center-middle"):
                yield SettingOption(
                    widget_id="managed-mounts-dir",
                    description="Directory to store managed mounts. \nChanging this"
                    " will prompt for options before committing changes.",
                    value_str="~/.config/systemd-mount-manager/managed-mounts",
                    setting_type=SettingType.INPUT,
                )
                yield SettingOption(
                    widget_id="smb-share",
                    description="The SMB share to mount (some extra info here)",
                    value_str="brents-data",
                    setting_type=SettingType.INPUT,
                )
                yield SettingOption(
                    widget_id="test-switch",
                    description="Test Switch. Does nothing.",
                    value_bool=False,
                    setting_type=SettingType.SWITCH,
                )
                with Horizontal(classes="save-cancel-buttons"):
                    yield Container()
                    yield Button("Save Changes", id="save-button")
                    yield Button("Cancel", id="cancel-button")
                    
    # def on_mount(self) -> None:
    #     self.load_settings()

    def load_settings(self) -> None:
        settings_payload = logic.load_settings()
        self.query_one("#managed-mounts-dir", Input).value = settings_payload.managed_mounts_dir
        # self.notify("Settings loaded")

    @on(Switch.Changed, "#test-switch")
    def switch_changed(self, event: Switch.Changed) -> None:
        self.notify(f"Switch {event.switch.id} changed to {event.value}")
        
    @on(Button.Pressed, "#save-button")
    def save_button_pressed(self, event: Button.Pressed) -> None:
        # Gather all the values from the widgets
        managed_mounts_dir = self.query_one("#managed-mounts-dir", Input).value
        
        settings_payload = logic.SettingsPayload(
            managed_mounts_dir=managed_mounts_dir
        )
        try:
            logic.save_settings(settings_payload)
        except Exception as e:
            self.log(f"Error saving settings: {e}")
            self.notify(f"Error saving settings: {e}")
            return
        
        self.log(f"Settings saved: {settings_payload}")
        self.notify("Settings saved")

    @on(Button.Pressed, "#cancel-button")
    def cancel_button_pressed(self, event: Button.Pressed) -> None:
        self.load_settings()
