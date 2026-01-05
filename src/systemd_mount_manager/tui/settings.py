"""
Contains the Settings tab for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations
from enum import Enum
from pathlib import Path

# from typing import Any  # , cast
# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on  # , log
from textual.app import ComposeResult
from textual.widgets import TabPane, Button, TextArea, Input
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    VerticalScroll,
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Switch, Input  # , Button, Select

import systemd_mount_manager.logic as logic

# [ ]: Add validation for input fields
# [ ]: managed-mounts-dir actually changes dir
# [ ]: Directory picker
# [ ]: Extra options modal when changing maaged-mounts-dir


class ChangeManagedMountsDirScreen(ModalScreen[None]):
    """This does not get launched unless the new dir is different from the current one"""

    BINDINGS = [
        Binding(
            "escape",
            "close_screen",
            description="Close the prompt and do nothing.",
            show=True,
        ),
    ]

    def __init__(self, new_managed_mounts_dir: str, current_managed_mounts_dir: str) -> None:
        super().__init__(classes="center-middle")
        self.new_managed_mounts_dir = new_managed_mounts_dir
        self.current_managed_mounts_dir = current_managed_mounts_dir

        # convert both to Path objects
        self.new_managed_mounts_dir = Path(self.new_managed_mounts_dir)
        self.current_managed_mounts_dir = Path(self.current_managed_mounts_dir)
        self.new_dir_exists = self.new_managed_mounts_dir.exists()

    def compose(self) -> ComposeResult:
        # We need to know:
        # Does the new dir already exist? Should it be created?
        # Does the user want to copy their existing mounts to the new dir?
        # Does the user want to delete the existing dir?
        # We need to do:
        # Grey out continue buttons and show message if proceeding is not possible
        # Validate input fields
        # Validate we have permissions to write to new dir
        # Create additional warning if user chooses not to migrate mounts

        with VerticalScroll(id="help-container"):
            yield Static("Change managed mounts directory", classes="inline-header")
            yield Static("\nCurrent:", classes="w1fr h2")
            yield TextArea(
                f"{self.current_managed_mounts_dir}",
                compact=True,
                soft_wrap=False,
                read_only=True,
            )
            yield Static("\nNew:", classes="w1fr h2")
            yield TextArea(
                f"{self.new_managed_mounts_dir}",
                compact=True,
                soft_wrap=False,
                read_only=True,
            )
            color = "green" if self.new_dir_exists else "red"
            yield Static(
                f"\nNew dir exists already: [{color}]{self.new_dir_exists}[/{color}]", classes="w1fr h2"
            )
            yield Static(classes="w1fr")
            with Horizontal(classes="option-box"):
                yield Static("Create new dir if it doesn't exist?", classes="h3 left-middle")
                yield Switch(id="create-new-dir")
            with Horizontal(classes="option-box"):
                yield Static(
                    "Migrate all managed mount files to new dir? \n"
                    "Existing files with matching names will be overwritten in the new directory, "
                    "and linked symlinks in /etc/systemd/system will be updated to match the new dir",
                )
                yield Switch(id="copy-existing-mounts")
            with Horizontal(classes="save-cancel-buttons"):
                yield Container()
                yield Button("Confirm", id="save-button")
                yield Button("Cancel", id="cancel-button")

    def action_close_screen(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#save-button")
    def save_button_pressed(self, event: Button.Pressed) -> None:
        self.notify("save_button_pressed")
        
    @on(Button.Pressed, "#cancel-button")
    def cancel_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

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

    @on(Switch.Changed, "#test-switch")
    def switch_changed(self, event: Switch.Changed) -> None:
        self.notify(f"Switch {event.switch.id} changed to {event.value}")

    @on(Button.Pressed, "#save-button")
    def save_button_pressed(self, event: Button.Pressed) -> None:
        something_changed = False
        # Gather all the values from the widgets
        new_managed_mounts_dir = self.query_one("#managed-mounts-dir", Input).value

        # Compare old managed mounts dir with new managed mounts dir
        current_managed_mounts_dir = logic.config["DEFAULT"]["managed_mounts_dir"]
        if current_managed_mounts_dir != new_managed_mounts_dir:
            result = self.app.push_screen(
                ChangeManagedMountsDirScreen(new_managed_mounts_dir, current_managed_mounts_dir)
            )
            return

        settings_payload = logic.SettingsPayload(managed_mounts_dir=new_managed_mounts_dir)
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
