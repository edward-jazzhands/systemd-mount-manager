"""
screens.py
This module defines the ColorScreen and HelpScreen classes
"""

# ~ Type Checking (Pyright and MyPy) - Strict Mode
# ~ Linting - Ruff
# ~ Formatting - Black - max 110 characters / line

# Python imports
from __future__ import annotations
from importlib import resources
import subprocess
from enum import Enum
from pathlib import Path

# Textual imports
# from textual import on
from textual.app import ComposeResult
from textual import on, work
import textual.events as events
from textual.containers import VerticalScroll, ScrollableContainer, Container, Horizontal
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Markdown, TabPane, Placeholder, Button, Static, Switch, TextArea


class HelpScreen(ModalScreen[None]):
    """Helpscreen class"""

    BINDINGS = [
        Binding("escape,enter", "close_screen", description="Close the help window.", show=True),
    ]

    def __init__(self, anchor: str | None = None) -> None:
        super().__init__(classes="center-middle")
        self.anchor_line = anchor

    def compose(self) -> ComposeResult:

        with resources.open_text("systemd_mount_manager", "help.md") as f:
            self.help = f.read()

        with VerticalScroll(classes="help-container"):
            yield Markdown(self.help)

    def on_mount(self) -> None:
        self.query_one(VerticalScroll).focus()
        if self.anchor_line:
            found = self.query_one(Markdown).goto_anchor(self.anchor_line)
            if not found:
                self.log.error(f"Anchor '{self.anchor_line}' not found in help document.")

    def on_click(self) -> None:
        self.dismiss()

    def action_close_screen(self) -> None:
        self.dismiss()




class SudoWarningScreenResult(Enum):
    PROCEED = 1
    PROCEED_DONT_SHOW_AGAIN = 2
    CANCEL = 3

class SudoWarningScreen(ModalScreen[SudoWarningScreenResult]):

    BINDINGS = [
        Binding(
            "escape",
            "close_screen",
            description="Close the prompt and do nothing.",
            show=True,
        ),
    ]

    def __init__(self, operation: str) -> None:
        """`operation` is a string describing the operation that requires elevated privileges
        It's only to describe the operation, not used for anything."""
        super().__init__(classes="center-middle")
        self.operation = operation 


    def compose(self) -> ComposeResult:

        with VerticalScroll(classes="help-container hauto"):
            yield Static("Attention: Priveleged operation", classes="inline-header")
            yield Static(
                f"\nThe operation:  [yellow]{self.operation}[/yellow]\n"
                "requires elevated privileges. The program will suspend "
                "back to the terminal and you'll be prompted for your password if it's not "
                "currently cached by your OS. \n\n"
                "This uses OS-level sudo caching, your password is never read by this app.\n"
                , classes="w1fr")
            with Horizontal(classes="option-box"):
                yield Static(
                    "Don't show this warning again for future privileged operations"
                )
                yield Switch(id="dont-show-again")
            # yield Container(classes="hauto")
            with Horizontal(classes="save-cancel-buttons"):
                yield Container()
                yield Button("Confirm", id="save-button")
                yield Button("Cancel", id="cancel-button")

    # The "click outside window to close" pattern
    def on_click(self, event: events.Click) -> None:
        if isinstance(event.widget, SudoWarningScreen):
            self.dismiss(SudoWarningScreenResult.CANCEL)

    def action_close_screen(self) -> None:
        self.dismiss(SudoWarningScreenResult.CANCEL)

    @on(Button.Pressed, "#cancel-button")
    def cancel_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(SudoWarningScreenResult.CANCEL)

    @on(Button.Pressed, "#save-button")
    def save_button_pressed(self, event: Button.Pressed) -> None:

        switch_value = self.query_one("#dont-show-again", Switch).value
        if switch_value:
            # If switch has been enabled, don't show again
            self.dismiss(SudoWarningScreenResult.PROCEED_DONT_SHOW_AGAIN)
        else:
            self.dismiss(SudoWarningScreenResult.PROCEED)

