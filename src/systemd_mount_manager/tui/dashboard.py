"""
Contains the dashboard for Systemd Mount Manager.
"""

# Python imports
from __future__ import annotations
from enum import Enum
from typing import cast

# import sys
# from dataclasses import dataclass

# Textual imports
from textual import on, work  # , log
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import TabPane, Button, ContentSwitcher

# from textual.binding import Binding
from textual.widgets import Static, DataTable  # , Switch  # , Button, Select
from rich.text import Text


# Local imports
import systemd_mount_manager.logic as logic
from systemd_mount_manager.logic.log_setup import logger

class ShareStatus(Enum):
    CONNECTED = 1
    IDLE = 2
    FAILED = 3


class ShareType(Enum):
    SMB = 1
    NFS = 2


class ManagedMountWidget(Horizontal):

    # UnitSection:
    #     description: str
    #     requires: str | None
    #     after: str | None

    # MountSection:
    #     what: str
    #     where: str
    #     type: str
    #     options: str
    #     timeoutsec: str

    # AutomountSection:
    #     where: str
    #     timeoutidlesec: str

    # InstallSection:
    #     wantedby: str

    def __init__(self, mount_data: logic.mounts.ManagedMountData) -> None:
        super().__init__()
        self.type: logic.mounts.MountType
        self.mount_data = mount_data
        if isinstance(mount_data.mount, logic.mounts.ManagedMountMountSection):
            self.type = logic.mounts.MountType.MOUNT_AT_BOOT
        else:  # must be MountType.MOUNT_LAZILY
            self.type = logic.mounts.MountType.AUTOMOUNT

    def compose(self) -> ComposeResult:
        yield Static(self.mount_data.unit.description, classes="mount-data-box")
        yield Static(self.mount_data.mount.where, classes="mount-data-box")
        yield Static(self.type, classes="mount-data-box")
        yield Static("UNKNOWN", classes="mount-data-box")


class ManagedMountHeader(Container):

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Managed Mounts", classes="w1fr margin-0-1")
            # yield Container()
            # yield Button("Button 1", id="button1", compact=True)
            # yield Button("Button 2", id="button2", compact=True)
            # yield Button("Button 3", id="button3", compact=True)

        # with Horizontal(id="mount-col-names"):
        #     yield Static("Name", classes="mount-data-box")
        #     yield Static("Mount Point", classes="mount-data-box")
        #     yield Static("Type", classes="mount-data-box")
        #     yield Static("Status", classes="mount-data-box")

    # @on(Button.Pressed, "#button1")
    # def button1_pressed(self) -> None:
    #     self.notify("button1_pressed")

    # @on(Button.Pressed, "#button2")
    # def button2_pressed(self) -> None:
    #     self.notify("button2_pressed")

    # @on(Button.Pressed, "#button3")
    # def button3_pressed(self) -> None:
    #     self.notify("button3_pressed")


class ManagedMounts(Container):

    # Ways to get mounts into program:
    # 1) Use add mount wizard page
    # 2) Copy and paste the files into managed mounts dir
    # 3) Detect existing mount files in /etc/systemd/system and offer to migrate them
    # 4) Get the mounts from /run/systemd/generator/*.mount (fstab mounts migration)
    # 5) Get the mounts from /run/systemd/transient/*.mount (transient mounts migration)

    def compose(self) -> ComposeResult:
        self.mounts_list = []
        logger.debug("Composing ManagedMounts")
        yield ManagedMountHeader(classes="h3")
        yield Container(id="managed-mounts-container")

    async def on_mount(self):
        logger.debug("Mounted ManagedMounts")

        worker = self.load_managed_mounts()
        self.mounts_list = await worker.wait()
        if not self.mounts_list:
            self.mount(Static("No mounts found", classes="no-mounts-found"))

    @work(exit_on_error=False)
    async def load_managed_mounts(self) -> list[logic.mounts.ManagedMountData]:
        """Loads the mounts from the managed mounts directory then updates the UI.
        Returns a list of ManagedMountData objects. This list is not connected to
        whether the UI was updated successfully."""

        logger.debug("Loading managed mounts")
        mounts_container = self.query_one("#managed-mounts-container", Container)
        managed_mounts = logic.mounts.list_managed_mounts_data()
        for mount_entry_data in managed_mounts:
            mounts_container.mount(ManagedMountWidget(mount_entry_data))
            # Note for anyone unfamiliar with Textual: .mount() is a method for updating
            # the TEXTUAL UI (mounting widgets in containers). It is completely unrelated to systemd.
            # The word `mount` just has special meaning in Textual. The dual meaning of the word
            # may appear confusing here. It's mounting a ManagedMountWidget in the Textual UI,
            # which is only a visual representation of its corresponding mount file.
            # This is not actually 'mounting' (aka installing/enabling) the mount units in systemd.
        return managed_mounts


class DiscoveredMountHeader(Horizontal):

    def compose(self) -> ComposeResult:
        yield Static("Discovered Mounts", classes="compact-static")
        yield Container()
        yield Button("Non-System Mounts", id="non-system-mounts-button", compact=True)
        yield Button("System Mounts", id="system-mounts-button", compact=True)
        yield Button("All Mounts", id="all-mounts-button", compact=True)
        yield Button("Refresh", id="refresh-button", compact=True)


class DiscoveredMounts(Container):

    class TableMode(Enum):
        NONSYSTEM = 1
        SYSTEM = 2
        ALL = 3

    def compose(self) -> ComposeResult:
        self.table_mode = DiscoveredMounts.TableMode.NONSYSTEM
        self.mounts_list: list[logic.mounts.MountTuple] = []
        self.managed_list: list[str] = []

        self.table = DataTable[str](id="discovered-mounts-table")
        self.table.add_column("Mount Type", key="mount_type")
        self.table.add_column("Unit", key="unit")
        self.table.add_column("Load", key="load")
        self.table.add_column("Active", key="active")
        self.table.add_column("Sub", key="sub")
        self.table.add_column("Description", key="description")
        self.table.cursor_type = "row"

        yield DiscoveredMountHeader(classes="h2")
        with ContentSwitcher(initial="discovered-mounts-table"):
            yield self.table
            yield Static(
                "No additional user mounts discovered",
                id="no-mounts-found",
                classes="no-mounts-found",
            )
            yield Static(
                "(DEBUG MODE) \nSystemD not found", id="sysd-not-found", classes="no-mounts-found"
            )

    async def on_mount(self):
        await self.refresh_data().wait()

    @on(Button.Pressed, "#refresh-button")
    @work(exit_on_error=False)
    async def refresh_data(self) -> None:
        try:
            self.mounts_list = logic.mounts.detect_all_systemd_mounts()
            self.managed_list = [mount.name for mount in logic.mounts.list_managed_mounts()]
        except OSError:
            self.sysd_not_found()
            return
        match self.table_mode:
            case DiscoveredMounts.TableMode.NONSYSTEM:
                self.show_nonsystem_mounts()
            case DiscoveredMounts.TableMode.SYSTEM:
                self.show_system_mounts()
            case DiscoveredMounts.TableMode.ALL:
                self.show_all_mounts()

    def sysd_not_found(self) -> None:
        self.query_one(ContentSwitcher).current = "sysd-not-found"
        self.query_one("#non-system-mounts-button").disabled = True
        self.query_one("#system-mounts-button").disabled = True
        self.query_one("#all-mounts-button").disabled = True
        self.query_one("#refresh-button").disabled = True

    @on(Button.Pressed, "#non-system-mounts-button")
    def show_nonsystem_mounts(self) -> None:
        logger.debug("Showing non-system mounts")
        self.table_mode = DiscoveredMounts.TableMode.NONSYSTEM
        first_filter = [
            mount
            for mount in self.mounts_list
            if not mount.unit.startswith(("sys-", "dev-", "proc-", "run-", "-."))
        ]
        unmanaged_filter = [mount for mount in first_filter if mount.unit not in self.managed_list]
        if not unmanaged_filter:
            self.query_one(ContentSwitcher).current = "no-mounts-found"
            return
        else:
            self.query_one(ContentSwitcher).current = "discovered-mounts-table"
            self.table.clear()
            self.table.add_rows(unmanaged_filter)

    @on(Button.Pressed, "#system-mounts-button")
    def show_system_mounts(self) -> None:
        logger.debug("Showing system mounts")
        self.table_mode = DiscoveredMounts.TableMode.SYSTEM
        self.query_one(ContentSwitcher).current = "discovered-mounts-table"
        self.table.clear()
        self.table.add_rows(
            [
                mount
                for mount in self.mounts_list
                if mount.unit.startswith(("sys-", "dev-", "proc-", "run-", "-."))
            ]
        )

    @on(Button.Pressed, "#all-mounts-button")
    def show_all_mounts(self) -> None:
        logger.debug("Showing all mounts")
        self.table_mode = DiscoveredMounts.TableMode.ALL
        self.query_one(ContentSwitcher).current = "discovered-mounts-table"
        self.table.clear()
        for mount in self.mounts_list:
            # highlight the managed mounts
            if mount.unit in self.managed_list:
                textized = Text(mount.unit, style="dark_orange")
                new_row = mount._replace(unit=textized)
                self.table.add_row(*new_row)
            else:
                self.table.add_row(*mount)


class DashBoard(TabPane):
    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="content-container"):
            logger.debug("Composing DashBoard")
            yield ManagedMounts(classes="card-container hauto horizontal-scroll")
            yield DiscoveredMounts(classes="card-container hauto")
