"""
Contains the Settings tab for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations
from enum import Enum
from pathlib import Path

# from asyncio import Await

from typing import Awaitable  # , cast

# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on, log, work
import textual.events as events
from textual.app import ComposeResult
from textual.widgets import TabPane, Button, TextArea, Input, Static, Switch
from textual.validation import ValidationResult, Validator  # , Function, Number
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    VerticalScroll,
)
from textual.binding import Binding
from textual.screen import ModalScreen

import systemd_mount_manager.logic as logic

# [ ]: Add validation for input fields
# [ ]: managed-mounts-dir actually changes dir
# [ ]: Directory picker
# [ ]: Extra options modal when changing maaged-mounts-dir


class ValidPath(Validator):
    def validate(self, value: str) -> ValidationResult:
        """Check that a value is a valid path."""

        if r"\0" in value:
            return self.failure("Invalid path: contains null character")

        if not value or not value.strip():
            return self.failure("Invalid path: empty or whitespace only")

        if not value.isprintable():
            return self.failure("Invalid path: contains non-printable characters")

        try:
            path = Path(value).expanduser()
        except Exception as e:
            return self.failure(f"Invalid path: {e}")

        if not path.is_absolute():
            return self.failure("Invalid path: not absolute")

        log(f"Valid path: {path.as_posix()}")
        return self.success()


class MountsDirScreenResult(Enum):
    PROCEED_WITHOUT_MIGRATE = 1
    PROCEED_WITH_MIGRATE = 2
    CANCEL = 3


class ChangeManagedMountsDirScreen(ModalScreen[MountsDirScreenResult]):
    """This does not get launched unless the new dir is different from the current one.
    Assumes the new mount dir has already been validated."""

    BINDINGS = [
        Binding(
            "escape",
            "close_screen",
            description="Close the prompt and do nothing.",
            show=True,
        ),
    ]

    def __init__(self, new_dir_path: Path, current_dir_path: Path) -> None:
        super().__init__(classes="center-middle")

        self.new_dir_path = new_dir_path
        self.current_dir_path = current_dir_path

    def compose(self) -> ComposeResult:
        # We need to know:
        #   Does the new dir already exist? Should it be created?
        #   Does the user want to copy their existing mounts to the new dir?
        # We need to do:
        #   Create additional warning if user chooses not to migrate mounts

        with VerticalScroll(classes="help-container hauto"):
            yield Static("Change managed mounts directory", classes="inline-header")
            yield Static("\nCurrent:", classes="w1fr h2")
            yield TextArea(
                f"{self.current_dir_path.as_posix()}",
                compact=True,
                soft_wrap=False,
                read_only=True,
            )
            yield Static("\nNew:", classes="w1fr h2")
            yield TextArea(
                f"{self.new_dir_path.as_posix()}",
                compact=True,
                soft_wrap=False,
                read_only=True,
            )
            if self.new_dir_path.exists():
                yield Static("\nNew dir exists already: [green]True[/green]", classes="w1fr h2")
            else:
                yield Static(
                    "\nNew dir exists already: [red]False[/red]  -  Operation will create it",
                    classes="w1fr h2",
                )
            yield Static(classes="w1fr")
            with Horizontal(classes="option-box"):
                yield Static(
                    "Migrate all managed mount files to new dir? \n"
                    "Existing files with matching names will be overwritten in the new directory, "
                    "and linked symlinks in /etc/systemd/system will be updated to match the new dir",
                )
                yield Switch(id="migrate-existing-mounts")
            yield Static(
                "This will not delete or modify anything in the current directory.",
                classes="w1fr h2",
            )
            with Horizontal(classes="save-cancel-buttons"):
                yield Container()
                yield Button("Confirm", id="save-button")
                yield Button("Cancel", id="cancel-button")

    # The "click outside window to close" pattern
    def on_click(self, event: events.Click) -> None:
        if isinstance(event.widget, ChangeManagedMountsDirScreen):
            self.dismiss(MountsDirScreenResult.CANCEL)

    def action_close_screen(self) -> None:
        self.dismiss(MountsDirScreenResult.CANCEL)

    @on(Button.Pressed, "#cancel-button")
    def cancel_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(MountsDirScreenResult.CANCEL)

    @on(Button.Pressed, "#save-button")
    def save_button_pressed(self, event: Button.Pressed) -> None:

        migrate = self.query_one("#migrate-existing-mounts", Switch).value
        if migrate:
            self.dismiss(MountsDirScreenResult.PROCEED_WITH_MIGRATE)
        else:
            self.dismiss(MountsDirScreenResult.PROCEED_WITHOUT_MIGRATE)


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
        validator: Validator | None = None,
    ) -> None:
        super().__init__()
        self.widget_id = widget_id
        self.description = description
        self.value_str = value_str
        self.value_bool = value_bool
        self.setting_type = setting_type
        self.validator = validator

    def compose(self) -> ComposeResult:
        with Horizontal(classes="setting-option-header"):
            yield Static(self.description, classes="setting-description")
            if self.setting_type == SettingType.SWITCH:
                yield Container()
                yield Switch(id=self.widget_id)
                self.add_class("h3")
        if self.setting_type == SettingType.INPUT:
            yield Input(
                self.value_str,
                id=self.widget_id,
                validators=self.validator,
                validate_on=["submitted", "blur"],
            )
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
                    validator=ValidPath(),
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
                    yield Button("Revert", id="cancel-button")

    # def on_mount(self) -> None:
    #     self.load_settings()

    def load_settings(self) -> None:
        settings_payload = logic.load_settings()
        self.query_one("#managed-mounts-dir", Input).value = settings_payload.managed_mounts_dir

    @on(Switch.Changed, "#test-switch")
    def switch_changed(self, event: Switch.Changed) -> None:
        self.notify(f"Switch {event.switch.id} changed to {event.value}")

    # @on(Input.Blurred, "#managed-mounts-dir")
    @on(Input.Submitted, "#managed-mounts-dir")
    def show_invalid_reasons(self, event: Input.Submitted) -> None:

        if event.validation_result and not event.validation_result.is_valid:
            for failure in event.validation_result.failure_descriptions:
                self.notify(failure)

    @on(Button.Pressed, "#save-button")
    @work(group="save-settings", exclusive=True, exit_on_error=True)
    async def save_button_pressed(self, event: Button.Pressed) -> None:

        something_changed = False
        # migrate = False

        # Gather references to all the settings widgets
        managed_mounts_dir_input = self.query_one("#managed-mounts-dir", Input)

        # Extract values from settings widgets
        new_dir_input = managed_mounts_dir_input.value

        # Normalize extracted values
        new_dir_path = Path(new_dir_input).expanduser()
        new_dir_as_posix = new_dir_path.as_posix()

        # Validate input fields
        validation_result = managed_mounts_dir_input.validate(new_dir_as_posix)
        assert validation_result is not None  # logically can't be None if validators are set
        if not validation_result.is_valid:
            for failure in validation_result.failure_descriptions:
                self.notify(failure)
            return

        # Compare old values with new values
        if new_dir_as_posix != logic.config["DEFAULT"]["managed_mounts_dir"]:
            current_dir_path = Path(logic.config["DEFAULT"]["managed_mounts_dir"])
            result = await self.app.push_screen_wait(
                ChangeManagedMountsDirScreen(new_dir_path, current_dir_path)
            )
            if result == MountsDirScreenResult.CANCEL:
                return
            migrate = result == MountsDirScreenResult.PROCEED_WITH_MIGRATE
            try:
                logic.change_managed_mounts_dir(new_dir_as_posix, migrate=migrate)
            except (ValueError, OSError) as e:
                self.log(f"Error: {e}")
                self.notify(f"Error: {e}")
                return
            something_changed = True

        if something_changed:
            self.log("Settings saved")
            self.notify("Settings saved")
        else:
            self.log("No settings changed, nothing to save.")
            self.notify("No settings changed, nothing to save.")

    @on(Button.Pressed, "#cancel-button")
    def cancel_button_pressed(self, event: Button.Pressed) -> None:
        self.load_settings()
