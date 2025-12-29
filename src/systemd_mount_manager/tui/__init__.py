from __future__ import annotations
import sys
from textual.app import App
import textual.events as events
from textual.widgets import Footer


class TextualApp(App[None]):   

    def __init__(self):         
        super().__init__()

    def on_load(self, event: events.Load) -> None:
        self.log("on_load: check")

    def compose(self):

        yield Footer()

    def on_resize(self, event: events.Resize) -> None:
        self.log("on_resize: check")  

    def on_mount(self, event: events.Mount) -> None:
        self.log("on_mount: check")   

    def on_ready(self, event: events.Ready) -> None:
        self.log("on_ready: check")   
        
        
def tui_run(debug: bool, fallback: bool) -> None:
    app = TextualApp()
    app.run()
    sys.exit(app.return_code)