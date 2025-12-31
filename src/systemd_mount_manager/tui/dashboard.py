"""
Contains the dashboard for Systemd Mount Manager.
"""
# Python imports
from __future__ import annotations
from enum import Enum
# from typing import Any  # , cast
# import sys
# from dataclasses import dataclass

# Textual imports
# from textual import on  # , log
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import TabPane, Placeholder
from textual.binding import Binding
from textual.widgets import Static, Switch  # , Button, Select


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
        share_status: ShareStatus
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
        yield Static("Managed Mounts")
        with Horizontal(id="mount-col-names"):
            yield Static("Name", classes="mount-data-box")
            yield Static("Target", classes="mount-data-box")
            yield Static("Type", classes="mount-data-box")
            yield Static("Status", classes="mount-data-box")    

class ManagedMounts(Container):
    
    def __init__(self) -> None:
        super().__init__()
        self.share_mounts: list[ManagedMount] = []
        
        # Dummy Data
        self.share_mounts.append(ManagedMount(
            "My Share 1",
            "//my-share/data",
            ShareType.SMB,
            ShareStatus.CONNECTED
        ))
        self.share_mounts.append(ManagedMount(
            "My Share 2",
            "//my-share2/data",
            ShareType.NFS,
            ShareStatus.IDLE
        ))
        self.share_mounts.append(ManagedMount(
            "My Share 3",
            "//my-share3/data",
            ShareType.SMB,
            ShareStatus.FAILED
        ))
        
            
    def compose(self) -> ComposeResult:
        
        yield ManagedMountHeader()
        for item in self.share_mounts:
            yield item


class DiscoveredMount(Horizontal):
    
    def __init__(
        self,
        share_name: str,
        share_target: str,
        share_type: ShareType,
        share_status: ShareStatus
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


class DiscoveredMountHeader(Container):
    
    def compose(self) -> ComposeResult:
        yield Static("Discovered Mounts")
        with Horizontal(id="mount-col-names"):
            yield Static("Name", classes="mount-data-box")
            yield Static("Target", classes="mount-data-box")
            yield Static("Type", classes="mount-data-box")
            yield Static("Status", classes="mount-data-box")    


class DiscoveredMounts(Container):
    
    def __init__(self) -> None:
        super().__init__()
        self.share_mounts: list[DiscoveredMount] = []
        
        # Dummy Data
        self.share_mounts.append(DiscoveredMount(
            "Discovered Share 1",
            "//discovered-share/data",
            ShareType.SMB,
            ShareStatus.CONNECTED
        ))
        self.share_mounts.append(DiscoveredMount(
            "Discovered Share 2",
            "//discovered-share2/data",
            ShareType.NFS,
            ShareStatus.IDLE
        ))
        self.share_mounts.append(DiscoveredMount(
            "Discovered Share 3",
            "//discovered-share3/data",
            ShareType.SMB,
            ShareStatus.FAILED
        ))
    
    def compose(self) -> ComposeResult:
        
        yield DiscoveredMountHeader()
        for item in self.share_mounts:
            yield item 


        
class DashBoard(TabPane):
    
    def compose(self) -> ComposeResult:
        with ScrollableContainer(classes="content-container"):
            yield ManagedMounts()
            yield DiscoveredMounts()