"""config.py - Contains logic for reading/writing config files"""

# python standard lib
from __future__ import annotations
from systemd_mount_manager.logic import config
from packaging.utils import _
import enum
from textwrap import dedent
import os
from pathlib import Path
from dataclasses import dataclass, replace
import errno
from threading import Lock
from collections import deque
from threading import Lock

# Third party
from pydantic import BaseModel, Field, ValidationError
from textual import log as textual_log
import yaml

# Local imports
import systemd_mount_manager.logic.core as core

# need to handle:

# Missing files
# Missing keys
# Malformed values
# Is path technically valid
# Is path actually writable
# Permissions issues reading the config file
# Concurrent modification
# Pop-up warnings if a config value has changed that requires an action

_config_lock = Lock()

class XDGDirectory(enum.StrEnum):
    """The valid env vars this program is concerned with for XDG paths.
    XDG spec env vars must be absolute paths.
    
    CONFIG: "XDG_CONFIG_HOME" - For config files
    STATE: "XDG_STATE_HOME" - For logs
    """

    CONFIG = "XDG_CONFIG_HOME"
    STATE = "XDG_STATE_HOME"


class DirectoriesEnum(enum.StrEnum):
    """Enum for directory types"""
    CONFIG = "config"
    LOGS = "logs"
    MANAGED_MOUNTS = "managed_mounts"

# Pydantic Models
class DirectoriesSchema(BaseModel):
    logs_dir: str
    managed_mounts_dir: str

class MiscSchema(BaseModel):
    show_sudo_warning: bool
    show_config_warning: bool
    textual_theme: str

class ConfigPayload(BaseModel):
    directories: DirectoriesSchema
    misc: MiscSchema


# Module level cache
# ==================

@dataclass(frozen=True)
class ConfigStorage:
    """Creates an immutable dataclass that serves as in-memory storage for the
    current config payload."""

    config: ConfigPayload | None = None

    def replace(self, config: ConfigPayload) -> ConfigStorage:
        """Return a new ConfigStorage object with the specified config payload"""
        return ConfigStorage(config=config)


config_storage = ConfigStorage(None)
"""Global config storage object. This object is immutable and thread-safe.
Use the `replace` method to create a new ConfigStorage object."""



# Default Configs Generation
# ==========================


def _get_dir_following_xdg_spec(xdg_env_var: XDGDirectory) -> Path:
    """
    Get a Path representing one of the supported directories following XDG spec.

    Remember to run expanduser() on the path if using it to create a file or directory.

    Priority:
    1. {xdg_env_var}/systemd-mount-manager (if the {xdg_env_var} is set)
    2. Default path (fallback)

    Args:
        xdg_env_var (XDGDirectory): The XDG environment variable to use
    Returns:
        Path | None: The resolved path, or None if there was an error
    """

    # xdg_env_var takes priority if set and valid
    if xdg_dir := os.getenv(xdg_env_var):
        xdg_path = Path(xdg_dir.strip())
        if xdg_path.is_absolute():
            return Path(xdg_dir.strip()) / "systemd-mount-manager"

    # If the XDG env var is not set or valid, then fallback to defaults.

    if xdg_env_var == XDGDirectory.CONFIG:
        dir_path = Path("~/.config/systemd-mount-manager")
    elif xdg_env_var == XDGDirectory.STATE:
        dir_path = Path("~/.local/state/systemd-mount-manager")

    return dir_path


# def _safely_resolve_path(path_obj: Path) -> Path | None:
#     """Safely resolve the path. This does not try to check if the path exists.
    
#     Errors could happen if the path is invalid and cannot be resolved. This
#     will log the error and return None.
#     """

#     try:
#         return path_obj.resolve()
#     except Exception as e:
#         e.add_note(f"Unable to resolve path: {path_obj}")
#         core.error_storage.add_error(e)
#         return None


def _generate_config_defaults_dict() -> ConfigPayload:
    """Generate a dict of default config values
    
    Returns:
        ConfigPayload: A dict of default config values
    """

    config_dir = _get_dir_following_xdg_spec(XDGDirectory.CONFIG)
    logs_dir = _get_dir_following_xdg_spec(XDGDirectory.STATE)

    return ConfigPayload(
        directories = DirectoriesSchema(
            logs_dir=str(logs_dir),
            managed_mounts_dir=str(config_dir / "managed-mounts"),
        ),
        misc = MiscSchema(
            show_sudo_warning=True,
            show_config_warning=True,
            textual_theme="textual-dark",
        )
    )

def _convert_dict_to_yaml_file(config_dict: ConfigPayload) -> str:
    """Convert a dict of config values to a YAML string

    Args:
        config_dict (ConfigPayload): The dict of config values
    Returns:
        str: A YAML string suitable to write out to a file, with comments included
    """

    return dedent(f"""\
    directories:
      # Default logs dir is ~/.local/state/systemd-mount-manager, unless XDG_STATE_HOME
      # is set when this file is generated.
      logs_dir: {config_dict.directories.logs_dir}

      # Default managed mounts dir is ~/.config/systemd-mount-manager/managed-mounts,
      # unless XDG_CONFIG_HOME is set when this file is generated.
      managed_mounts_dir: {config_dict.directories.managed_mounts_dir}

    misc:
      # When true, the program will warn you before performing any operation that
      # requires you to suspend out to the terminal and enter your password.
      show_sudo_warning: {config_dict.misc.show_sudo_warning}

      # When true, the program will warn you before allowing you to make changes
      # to this config file using the in-app settings menu. This is because using
      # the settings menu will set all comments in this file back to defaults.
      show_config_warning: {config_dict.misc.show_config_warning}

      # The theme to use for the TUI. See available themes in the settings menu.
      textual_theme: {config_dict.misc.textual_theme}
    """)



def _create_default_config_file() -> bool:
    """This will create a default config file in the user's config directory
    if there is not already a config file present.

    Args:
        config_dir (Path): The path to the config directory (use the
            `_get_dir_following_xdg_spec` function to get this)
    Returns:
        bool: True if the file was created, False if it already existed
    Raises:
        OSError: if there is a problem creating the config file or config directory
        ValueError: if the config directory is not set
    """

    config_dir = _get_dir_following_xdg_spec(XDGDirectory.CONFIG).expanduser()
    config_file_path = config_dir / "config.yaml"

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        core.os_error_logger(e, "create", "config directory")
        raise e

    try:
        with open(config_file_path, "x") as f: # x = exclusive
            f.write(_convert_dict_to_yaml_file(_generate_config_defaults_dict()))
    except FileExistsError:
        return False
    except OSError as e:
        # Any OS error here means the file doesn't exist but we couldn't
        # create it for some reason.
        core.os_error_logger(e, "create", "config file")
        raise e

    # If we got here then a new file was written successfully
    return True
        

def config_startup() -> bool:
    """Program startup logic API for the config module

    Returns:
        bool: True if config startup was sucessful, False if there was an error.
    Raises:
        Nothing. Should catch errors without raising.
    """

    creation_result: bool | None = None
    try:
        creation_result = _create_default_config_file()
    except Exception as e:
        # This means we couldn't create either the config dir or the config file.
        e.add_note(f"Error in startup! Couldn't create a config file. See logs for details.")
        return False
    
    global config_storage
    # If we got here then we know we have a config dir and a config file.
    if creation_result is True:
        # True means we created a new config file with default values.
        # So we don't need to parse the config file, we can load the defaults
        # straight into memory.
        config_storage = ConfigStorage(_generate_config_defaults_dict())
    elif creation_result is False:
        # False means there was an existing config file.
        # We must parse it.
        try:
            config_storage = ConfigStorage(read_config_file())
        except Exception as e:
            e.add_note(f"Error in startup! Couldn't read your config file. See logs for details.")
            return False
    
    return True


def read_config_file() -> ConfigPayload:
    """Read the config file and return a ConfigPayload object (pydantic model)
    
    Returns:
        ConfigPayload: The config file contents
    Raises:
        OSError: if there is a problem reading the config file or resolving its path
        yaml.YAMLError: if the config file is not valid YAML
        ValidationError: if the config file fails pydantic validation
    """
    # Note to self: by catching the errors here, we can differentiate between:
    # - error opening the file (permission issues)
    # - error parsing the file (malformed YAML)
    # - error validating the file (malformed values)

    config_dir = _get_dir_following_xdg_spec(XDGDirectory.CONFIG).expanduser()
    config_file_path = config_dir / "config.yaml"

    try:
        f = open(config_file_path, "r")
    except OSError as e:
        # Any kind of error trying to read this file is a breaking error.
        core.os_error_logger(e, "read", "config file")
        raise e

    try:
        config_dict = yaml.safe_load(f)    
        return ConfigPayload(**config_dict)
    except (yaml.YAMLError, ValidationError) as e:
        e.add_note(f"Error trying to parse config file at: {config_dir}")
        core.error_storage.add_error(e)
        raise e
        


def change_managed_mounts_dir(new_dir: str, migrate: bool = False) -> bool:
    """Change the managed mounts directory. Resolves the past in new_dir
    and attempts to create the new directory.

    Args:
        new_dir (str): The new directory path
        migrate (bool, optional): If True, the existing files will be moved to the new directory.
    Returns:
        bool: True if everything was successful. No path to return False at the moment.
    Raises:
        OSError: if there is a problem creating the new directory
    """

    # First convert the string to a path object
    new_path = Path(new_dir)

    try:
        new_path.resolve().mkdir(parents=True, exist_ok=True)
    except OSError as e:
        core.os_error_logger(e, "create", "directory")
        raise e

    try:
        testfile = new_path / ".testfile"
        testfile.touch()
        testfile.unlink()
    except OSError as e:
        core.os_error_logger(e, "create", "directory")
        raise e

    if migrate:
        # here add migrate logic when ready
        pass

    # If migration was skipped or successful then we can update the user config file
    # config.set("DEFAULT", "managed_mounts_dir", new_dir)

    # config_path = get_config_path(USER_CONFIG_FILE_NAME)
    # try:
    #     with open(config_path, "w") as configfile:
    #         config.write(configfile)
    # except OSError as e:
    #     os_error_handler(e, "modify", "config file")

    return True
