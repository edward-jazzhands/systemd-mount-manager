"""config.py - Contains logic for reading/writing config file
Import the `config` object from this module to read configs from configparser obj."""

# python standard lib
from __future__ import annotations
# import sys
# from typing import Sequence
# import subprocess
# import json
from pathlib import Path
from dataclasses import dataclass
# from enum import StrEnum
# from textwrap import dedent
import errno
import configparser

# Third party
# import rich.rule
from textual import log
# import rich 


SYSTEMD_PATH: Path = Path("/etc/systemd/system/")
HOME: Path = Path.home()
SMM_PATH: Path = HOME / ".config" / "systemd-mount-manager"
CONFIG_PATH = SMM_PATH / "config.ini"
DEFAULT_MOUNTFILES_DIR: Path = SMM_PATH / "managed-mounts"


class TextualLogWriter:

    def __init__(self) -> None:
        self.buffer: list[str] = []

    def flush(self) -> None:
        "write collected messages to terminal"
        log_string = "".join(self.buffer)
        log(log_string.rstrip("\n"))
        self.buffer = []

    def write(self, message: str) -> None:
        self.buffer.append(message)
_log_writer = TextualLogWriter()


@dataclass
class SettingsPayload:
    managed_mounts_dir: str
    hide_startup_gui_warning: bool


config = configparser.ConfigParser()
# If this is first run, this file will not exist yet and this will do nothing:
read_files = config.read(CONFIG_PATH)


# A small helper to log current config to Textual console, for debugging
def textual_log_config_file(config_parser: configparser.ConfigParser = config) -> None:
    log("Config file:")
    config_parser.write(_log_writer)
    _log_writer.flush()


def write_default_config(force: bool = False) -> bool:
    """Run this for first time setup. Default configs will be loaded
    into configparser and written to config.ini

    Args:
        force (bool, optional): Force overwrite of existing config file. Defaults to False.
    Raises:
        FileExistsError: if config file already exists and force is False
    Returns:
        bool: True if config file was created, False if it already existed (overwrite)
    """

    # First create the SMM_PATH if it doesn't exist
    if not SMM_PATH.exists():
        SMM_PATH.mkdir(parents=True)

    # Create default mountfiles dir if it doesn't exist
    if not DEFAULT_MOUNTFILES_DIR.exists():
        DEFAULT_MOUNTFILES_DIR.mkdir(parents=True)

    config_already_existed = False
    if CONFIG_PATH.exists():
        if not force:
            raise FileExistsError(f"Config file already exists: {CONFIG_PATH.as_posix()}")
        config_already_existed = True

    # Here create the default config
    config["DEFAULT"] = {
        "managed_mounts_dir": DEFAULT_MOUNTFILES_DIR.as_posix(),
        "hide_startup_gui_warning": "False"
    }
    with open(CONFIG_PATH, "w") as configfile:
        config.write(configfile)

    if config_already_existed:  # then we overwrote it (we return False)
        return False
    else:  # otherwise we created it. (We return True)
        return True


def load_settings() -> SettingsPayload:
    """Load settings from config file. Returns a SettingsPayload object.
    Import the SettingsPayload dataclass for type checking."""

    return SettingsPayload(
        managed_mounts_dir=config["DEFAULT"]["managed_mounts_dir"], 
        hide_startup_gui_warning=config["DEFAULT"]["hide_startup_gui_warning"]
    )


def change_managed_mounts_dir(new_dir: str, migrate: bool = False):
    """Change the managed mounts directory

    Raises:
        ValueError: if new_dir is the same as the current dir
        OSError: if there is a problem creating the new directory
    """

    # First convert the string to a path object
    new_path = Path(new_dir).resolve()

    # Ensure new dir is not the same as the current dir
    if config["DEFAULT"]["managed_mounts_dir"] == new_dir:
        raise ValueError("New managed mounts dir is the same as the current dir")

    try:
        new_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log.error(e)
        match e.errno:
            case errno.ENOSPC:
                raise OSError("Cannot create directory: No space left on device") from e
            case errno.EROFS:
                raise OSError("Cannot create directory: Read-only filesystem") from e
            case errno.ENAMETOOLONG:
                raise OSError("Cannot create directory: Path name too long") from e
            case errno.EACCES | errno.EPERM:
                raise OSError("Cannot create directory: Permission denied") from e
            case errno.EEXIST:
                raise OSError("Cannot create directory: A file exists at that location") from e
            case errno.ENOTDIR:
                raise OSError("Cannot create directory: Invalid parent path (file in path)") from e
            case errno.ESTALE:
                raise OSError(
                    "Cannot create directory: Network mount is stale or unavailable"
                ) from e
            case errno.EHOSTUNREACH | errno.EHOSTDOWN | errno.ENETUNREACH | errno.ENETDOWN:
                raise OSError("Cannot create directory: Network or host is unreachable") from e
            case errno.EIO:
                raise OSError(
                    "Cannot create directory: I/O error (possible network or disk issue)"
                ) from e
            case _:
                raise OSError(f"Cannot create directory: {e}") from e

    try:
        testfile = new_path / ".testfile"
        testfile.touch()
        testfile.unlink()
    except OSError as e:
        log.error(e)
        match e.errno:
            case errno.ENOSPC:
                raise OSError("Directory change failed: No space left on device") from e
            case errno.EROFS:
                raise OSError("You can't write to that directory: Read-only filesystem") from e
            case errno.EACCES | errno.EPERM:
                raise OSError("You don't have permission to write to that directory") from e
            case _:
                raise OSError(f"Error changing directory: {e}") from e

    if migrate:
        # here add migrate logic when ready
        pass

    # If migration was skipped or successful then we can update the config file
    config["DEFAULT"]["managed_mounts_dir"] = new_dir
    with open(CONFIG_PATH, "w") as configfile:
        config.write(configfile)

def change_hide_startup_gui_warning(new_value: bool):

    # config["DEFAULT"]["hide_startup_gui_warning"] = new_value
    config.set
    with open(CONFIG_PATH, "w") as configfile:
        config.write(configfile)