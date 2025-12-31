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

# Textual imports
# from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Markdown


class HelpScreen(ModalScreen[None]):
    """Helpscreen class"""

    BINDINGS = [
        Binding("escape,enter", "close_screen", description="Close the help window.", show=True),
    ]

    def __init__(self, anchor: str | None = None) -> None:
        super().__init__()
        self.anchor_line = anchor

    def compose(self) -> ComposeResult:

        with resources.open_text("systemd_mount_manager", "help.md") as f:
            self.help = f.read()

        with VerticalScroll(id="help_container"):
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
