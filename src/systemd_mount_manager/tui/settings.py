"""
Contains the Settings tab for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations
from collections.abc import Iterable
from enum import Enum
from pathlib import Path

# from asyncio import Await

# from typing import Awaitable  # , cast

# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on, log, work
import textual.events as events
from textual.app import ComposeResult
from textual.widgets import TabPane, Button, TextArea, Input, Static, Switch
from textual.widgets._input import InputValidationOn
from textual.validation import ValidationResult, Validator  # , Function, Number
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    VerticalScroll,
)
from textual.binding import Binding
from textual.screen import ModalScreen
import textual_fspicker as fspicker
import textual_fspicker.parts as fspicker_parts

# Local imports
import systemd_mount_manager.logic as logic
from systemd_mount_manager.logic.log_setup import logger


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
            path = Path(value).resolve()
        except Exception as e:
            return self.failure(f"Invalid path: {e}")

        if not path.is_absolute():
            return self.failure("Invalid path: not absolute")

        log(f"Valid path resolved: {path.resolve().as_posix}")
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

        with VerticalScroll(classes="help-container hauto"):
            yield Static("Change managed mounts directory", classes="inline-header")
            yield Static("\nCurrent:", classes="w1fr h2")
            yield TextArea(
                f"{self.current_dir_path}",
                compact=True,
                soft_wrap=False,
                read_only=True,
            )
            yield Static("\nNew:", classes="w1fr h2")
            yield TextArea(
                f"{self.new_dir_path}",
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
            with Horizontal(classes="save-cancel-buttons h3"):
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


class CustomFSPicker(fspicker.SelectDirectory):

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""
        navigation = self.query_one(fspicker_parts.DirectoryNavigation)
        navigation.show_files = False
        navigation.show_hidden = True
        self.query_one(fspicker_parts.CurrentDirectory).current_directory = navigation.location


class SettingsTab(TabPane):

    _validate_on: list[InputValidationOn] = ["submitted", "blur"]

    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            with Container(id="settings-container", classes="card-container hauto center-middle"):

                with Container(classes="setting-option hauto"):
                    # with Horizontal(classes="setting-option-header"):
                    yield Static(
                        "Directory to store managed mounts \nChanging this"
                        " will prompt for options before committing changes.",
                        classes="setting-description",
                    )
                    with Horizontal(classes="hauto margin-1-0"):
                        yield Static("Open directory picker", classes="compact-static")
                        yield Button("Choose", id="fspicker-button", compact=True)
                        yield Container(classes="h1")

                    yield Input(
                        id="managed-mounts-dir",
                        validators=ValidPath(),
                        validate_on=SettingsTab._validate_on,
                    )
                    with Horizontal(classes="save-cancel-buttons h1"):
                        yield Container()
                        yield Button("Save Changes", id="save-dir-button", compact=True)
                        yield Button("Revert", id="revert-dir-button", compact=True)

                with Horizontal(classes="setting-option hauto"):
                    yield Static(
                        "Show warning before performing privileged operations. \n"
                        "This does not affect whether you'll be prompted for your password "
                        "by your OS. The password is never read by this app.",
                        classes="setting-description",
                    )
                    # yield Container()
                    yield Switch(id="sudo-warning-switch")

                with Horizontal(classes="setting-option h3"):

                    yield Container()
                    yield Button("Test button", id="test-button")

    def on_mount(self) -> None:
        self.load_settings()

    def load_settings(self) -> None:
        pass
        # conf_data = logic.config.read_config()

        # if conf_data.managed_mounts_dir:
        #     self.query_one("#managed-mounts-dir", Input).value = conf_data.managed_mounts_dir
        # else:
        #     logger.debug("Warning: managed mounts dir could not be read from config file")
        # if conf_data.show_sudo_warning:
        #     self.query_one("#sudo-warning-switch", Switch).value = conf_data.show_sudo_warning
        # else:
        #     logger.debug("Warning: show sudo warning could not be read from config file")

    @on(Button.Pressed, "#fspicker-button")
    @work(exit_on_error=False)
    async def fspicker_button_pressed(self, event: Button.Pressed) -> None:

        picker_instance = CustomFSPicker(location=Path.home())
        result = await self.app.push_screen_wait(picker_instance)
        if result:
            self.query_one("#managed-mounts-dir", Input).value = result.as_posix()

    @on(Switch.Changed, "#sudo-warning-switch")
    def switch_changed(self, event: Switch.Changed) -> None:
        logger.debug(f"Switch {event.switch.id} changed to {event.value}")
        # logic.config.config.set("DEFAULT", "show_sudo_warning", str(event.value))

    # @on(Input.Blurred, "#managed-mounts-dir")
    @on(Input.Submitted, "#managed-mounts-dir")
    def show_invalid_reasons(self, event: Input.Submitted) -> None:

        if event.validation_result and not event.validation_result.is_valid:
            for failure in event.validation_result.failure_descriptions:
                self.notify(failure)

    @on(Button.Pressed, "#save-dir-button")
    @work(group="save-settings", exclusive=True, exit_on_error=True)
    async def save_button_pressed(self, event: Button.Pressed) -> None:

        dir_input_widget = self.query_one("#managed-mounts-dir", Input)
        new_dir_str = dir_input_widget.value

        something_changed = False

        # Normalize extracted value
        new_dir_path = Path(new_dir_str).resolve()

        # Validate input field
        validation_result = dir_input_widget.validate(str(new_dir_path))
        assert validation_result is not None  # logically can't be None if validators are set
        if not validation_result.is_valid:
            for failure in validation_result.failure_descriptions:
                self.notify(failure)
            return

        # Compare old value with new value
        # current_dir = logic.config.config["DEFAULT"]["managed_mounts_dir"]
        #! TEMPORARY
        current_dir = logic.config.default_config.managed_mounts_dir
        current_dir_path = Path(current_dir)
        if current_dir != new_dir_str:

            result = await self.app.push_screen_wait(
                ChangeManagedMountsDirScreen(new_dir_path, current_dir_path)
            )
            if result == MountsDirScreenResult.CANCEL:
                return
            migrate = result == MountsDirScreenResult.PROCEED_WITH_MIGRATE
            # try:
            #     logic.config.change_managed_mounts_dir(new_dir_as_posix, migrate=migrate)
            # except (ValueError, OSError) as e:
            #     logger.debug(f"Error: {e}")
            #     self.notify(f"Error: {e}")
            #     return
            something_changed = True

        if something_changed:
            logger.debug("Settings saved")
            self.notify("Settings saved")
        else:
            logger.debug("No settings changed, nothing to save.")
            self.notify("No settings changed, nothing to save.")

    @on(Button.Pressed, "#cancel-button")
    def cancel_button_pressed(self, event: Button.Pressed) -> None:
        self.load_settings()
