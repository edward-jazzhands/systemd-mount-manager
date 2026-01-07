"""
Contains the dashboard for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations
from enum import Enum
from typing import NamedTuple  # , cast

# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on, work  # , log
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import TabPane, Placeholder, Button
from textual.binding import Binding
from textual.widgets import Static, DataTable, Switch  # , Button, Select

# Local imports
import systemd_mount_manager.logic as logic


class ShareStatus(Enum):
    CONNECTED = 1
    IDLE = 2
    FAILED = 3


class ShareType(Enum):
    SMB = 1
    NFS = 2


class ManagedMount(Horizontal):
    def __init__(
        self,
        share_name: str,
        share_target: str,
        share_type: ShareType,
        share_status: ShareStatus,
    ) -> None:
        super().__init__()
        self.share_name = share_name
        self.share_target = share_target
        self.share_type = share_type
        self.share_status = share_status

    def compose(self) -> ComposeResult:
        yield Static(self.share_name, classes="mount-data-box share-name")
        yield Static(self.share_target, classes="mount-data-box share-type")
        yield Static(self.share_type.name, classes="mount-data-box share-target")
        yield Static(self.share_status.name, classes="mount-data-box share-status")


class ManagedMountHeader(Container):
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Managed Mounts", classes="compact-static")
            yield Container()
            yield Button("Button 1", id="button1", compact=True)
            yield Button("Button 2", id="button2", compact=True)
            yield Button("Button 3", id="button3", compact=True)

        with Horizontal(id="mount-col-names"):
            yield Static("Name", classes="mount-data-box")
            yield Static("Target", classes="mount-data-box")
            yield Static("Type", classes="mount-data-box")
            yield Static("Status", classes="mount-data-box")

    @on(Button.Pressed, "#button1")
    def button1_pressed(self) -> None:
        self.notify("button1_pressed")

    @on(Button.Pressed, "#button2")
    def button2_pressed(self) -> None:
        self.notify("button2_pressed")

    @on(Button.Pressed, "#button3")
    def button3_pressed(self) -> None:
        self.notify("button3_pressed")


class ManagedMounts(Container):
    def __init__(self) -> None:
        super().__init__(classes="card-container")
        self.share_mounts: list[ManagedMount] = []

        # Dummy Data
        self.share_mounts.append(
            ManagedMount("My Share 1", "//my-share/data", ShareType.SMB, ShareStatus.CONNECTED)
        )
        self.share_mounts.append(
            ManagedMount("My Share 2", "//my-share2/data", ShareType.NFS, ShareStatus.IDLE)
        )
        self.share_mounts.append(
            ManagedMount("My Share 3", "//my-share3/data", ShareType.SMB, ShareStatus.FAILED)
        )

    def compose(self) -> ComposeResult:
        yield ManagedMountHeader(classes="h3")
        for item in self.share_mounts:
            yield item


class DiscoveredMount(Horizontal):
    def __init__(
        self,
        share_name: str,
        share_target: str,
        share_type: ShareType,
        share_status: ShareStatus,
    ) -> None:
        super().__init__()
        self.share_name = share_name
        self.share_target = share_target
        self.share_type = share_type
        self.share_status = share_status

    def compose(self) -> ComposeResult:
        yield Static(self.share_name, classes="mount-data-box share-name")
        yield Static(self.share_target, classes="mount-data-box share-type")
        yield Static(self.share_type.name, classes="mount-data-box share-target")
        yield Static(self.share_status.name, classes="mount-data-box share-status")


class DiscoveredMountHeader(Horizontal):

    def compose(self) -> ComposeResult:
        yield Static("Discovered Mounts", classes="compact-static")
        yield Container()
        yield Button("Non-System Mounts", id="non-system-mounts-button", compact=True)
        yield Button("Active Mounts", id="active-mounts-button", compact=True)
        yield Button("All Mounts", id="all-mounts-button", compact=True)


class DiscoveredMounts(Container):
    def __init__(self) -> None:
        super().__init__(classes="card-container")
        self.share_mounts: list[DiscoveredMount] = []

    def compose(self) -> ComposeResult:
        self.table = DataTable[str](id="existing-mounts-table")
        self.table.add_column("Unit", key="unit")
        self.table.add_column("Load", key="load")
        self.table.add_column("Active", key="active")
        self.table.add_column("Sub", key="sub")
        self.table.add_column("Description", key="description")
        self.table.cursor_type = "row"

        yield DiscoveredMountHeader(classes="h2")
        yield self.table

    async def on_mount(self):
        worker = self.load_existing_mounts()
        self.mounts_list = await worker.wait()
        self.show_nonsystem_mounts(self.mounts_list)

    @work(exit_on_error=False)
    async def load_existing_mounts(self) -> list[logic.SystemctlListUnitsLine]:
        # NOTE: Add error handling at some point.
        return logic.detect_exising_mounts()  #    existing is a list of NamedTuples

    def show_nonsystem_mounts(self, mounts_list: list[logic.SystemctlListUnitsLine]) -> None:
        self.table.clear()
        # add_rows takes an iterable of iterables
        self.table.add_rows(
            [
                mount
                for mount in mounts_list
                if not mount.unit.startswith(("sys-", "dev-", "proc-", "run-", "-."))
            ]
        )

    def show_all_mounts(self, mounts_list: list[logic.SystemctlListUnitsLine]) -> None:
        self.table.clear()
        self.table.add_rows(mounts_list)

    def show_active_mounts(self, mounts_list: list[logic.SystemctlListUnitsLine]) -> None:
        self.table.clear()
        self.table.add_rows([mount for mount in mounts_list if mount.active == "active"])

    @on(Button.Pressed, "#non-system-mounts-button")
    def non_system_mounts_button_pressed(self) -> None:
        self.show_nonsystem_mounts(self.mounts_list)

    @on(Button.Pressed, "#active-mounts-button")
    def active_mounts_button_pressed(self) -> None:
        self.show_active_mounts(self.mounts_list)

    @on(Button.Pressed, "#all-mounts-button")
    def all_mounts_button_pressed(self) -> None:
        self.show_all_mounts(self.mounts_list)


class DashBoard(TabPane):
    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            yield ManagedMounts()
            yield DiscoveredMounts()
