"""config.py - Contains logic for reading/writing config files"""

# python standard lib
from __future__ import annotations
from typing import Any
import enum
import os
import tomllib
from pathlib import Path
from dataclasses import dataclass  # , replace

# Third party
from pydantic import BaseModel, ValidationError, TypeAdapter, ConfigDict
import tomlkit
import tomlkit.exceptions
import tomlkit.items

# Local imports
import systemd_mount_manager.logic.core as core

# CONSTANTS
DEFAULT_SYS_CONFIG_DIR = "~/.config"
DEFAULT_SYS_LOGS_DIR = "~/.local/state"
APP_NAME = core.APP_NAME


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


# Pydantic Model
class UserConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    logs_dir: str
    managed_mounts_dir: str
    show_sudo_warning: bool
    textual_theme: str


class ConfigStatus(enum.StrEnum):
    """Status of each config field

    | Status | String | Meaning |
    | ------ | ------ | ------- |
    | VALID | "valid" | The field exists and is valid |
    | MISSING | "missing" | The field is not present in the config file |
    | EMPTY | "empty" | The field is present but has an empty value |
    | INVALID | "invalid" | The field is present but failed validation |
    | NONEXISTENT | "nonexistent" | The field is not used by the program |
    | NOTYPE | "notype" | The field is used by the program but has no type annotation |
    """

    VALID = "valid"
    MISSING = "missing"
    EMPTY = "empty"
    INVALID = "invalid"
    NONEXISTENT = "nonexistent"
    NOTYPE = "notype"


default_config = UserConfig(
    logs_dir=f"{DEFAULT_SYS_LOGS_DIR}/{APP_NAME}",
    managed_mounts_dir=f"{DEFAULT_SYS_CONFIG_DIR}/{APP_NAME}",
    show_sudo_warning=True,
    textual_theme="textual-dark",
)
"default_config is a UserConfig object with default values"


DEFAULT_CONFIG_TOML = f"""\
# Any field that is missing (eg. commented out) or empty will use the default value.
# Uncomment a field to change its value.

[directories]
# Default is $XDG_STATE_HOME/systemd-mount-manager if $XDG_STATE_HOME is set, 
# otherwise default is {DEFAULT_SYS_LOGS_DIR}/{APP_NAME}.
# logs_dir = '{default_config.logs_dir}'

# Default is $XDG_CONFIG_HOME/systemd-mount-manager if $XDG_STATE_HOME is set, 
# otherwise default is {DEFAULT_SYS_CONFIG_DIR}/{APP_NAME}.
# managed_mounts_dir = '{default_config.managed_mounts_dir}'

[misc]
# When true, the program will warn you before performing any operation that
# requires you to suspend out to the terminal and enter your password.
# Default is true.
# show_sudo_warning = {default_config.show_sudo_warning}

# The theme to use for the TUI. See available themes in the settings menu.
# Default is 'textual-dark'.
# textual_theme = {default_config.textual_theme}
"""


# Module level cache
# ==================


@dataclass(frozen=True)
class ConfigStorage:
    """Creates an immutable dataclass that serves as in-memory storage for the
    current config payload. If no argument is provided, it will use default_config."""

    config: UserConfig = default_config
    parsing_stage_completed: bool = False

    def replace(self, config: UserConfig, parsing_stage_completed: bool) -> ConfigStorage:
        """Return a new ConfigStorage object with the specified config payload"""
        return ConfigStorage(config=config, parsing_stage_completed=parsing_stage_completed)


config_storage = ConfigStorage(default_config)
"""Global config storage object. This object is immutable and thread-safe.
Use the `replace` method to create a new ConfigStorage object."""


# Default Configs Generation
# ==========================


def _get_dir_following_xdg_spec(xdg_env_var: XDGDirectory) -> Path:
    """
    Get a Path representing one of the supported directories following XDG spec.

    Priority:
    1. {xdg_env_var}/systemd-mount-manager (if the {xdg_env_var} is set)
    2. Default path (fallback)

    Args:
        xdg_env_var (XDGDirectory): The XDG environment variable to use
    Returns:
        Path: The absolute path INCLUDING the app name
    """

    # xdg_env_var takes priority if set and valid
    if xdg_dir := os.getenv(xdg_env_var):
        xdg_path = Path(xdg_dir.strip())
        if xdg_path.is_absolute():
            return Path(xdg_dir.strip()) / APP_NAME

    # If the XDG env var is not set or valid, then fallback to defaults.

    if xdg_env_var == XDGDirectory.CONFIG:
        dir_path = Path(DEFAULT_SYS_CONFIG_DIR).expanduser() / APP_NAME
    elif xdg_env_var == XDGDirectory.STATE:
        dir_path = Path(DEFAULT_SYS_LOGS_DIR).expanduser() / APP_NAME

    return dir_path


def _create_default_config_file() -> bool:
    """This will create a default config file in the user's config directory
    if there is not already a config file present.

    Returns:
        bool: True if the file was created, False if it already existed
    Raises:
        OSError: if there is a problem creating the config file or config directory
        ValueError: if the config directory is not set
    """

    config_dir = _get_dir_following_xdg_spec(XDGDirectory.CONFIG)
    config_file_path = config_dir / "config.toml"

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        core.os_error_logger(e, "create", "config directory")
        raise e

    try:
        with open(config_file_path, "x") as f:  # x = exclusive
            f.write(DEFAULT_CONFIG_TOML)
    except FileExistsError:
        return False
    except OSError as e:
        # Any OS error here means the file doesn't exist but we couldn't
        # create it for some reason.
        core.os_error_logger(e, "create", "config file")
        raise e

    # If we got here then a new file was written successfully
    return True


def startup_config() -> bool:
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
        core.error_storage.add_error(e)
        return False

    # If we got here, then we know we have a config dir and a config file
    # that we can access.

    global config_storage

    if creation_result is True:
        # If creation_result is True, we created a new config file with default values.
        # We still need to mark that the parsing stage has been completed.
        config_storage = ConfigStorage(parsing_stage_completed=True)
    else:
        # False means there was an existing config file.
        # We must parse it.
        try:
            config_storage = ConfigStorage(read_config_file(), parsing_stage_completed=True)
        except Exception as e:
            e.add_note(f"Error in startup! Couldn't read your config file. See logs for details.")
            core.error_storage.add_error(e)
            return False

    return True


def read_config_file() -> UserConfig:
    """Read the config file and return a UserConfig object (pydantic model).

    Note to future self / other programmers: This is designed to be re-usable.
    It calls the `safely_parse_TOMLDocument` function, which is designed to
    take a TOMLDocument object and a Pydantic model.

    Returns:
        UserConfig: The config file contents
    Raises:
        OSError: if there is a problem reading the config file or resolving its path
        tomlkit.exceptions.TOMLKitError: if the config file is not valid TOML
        ValidationError: if the config file fails pydantic validation
    """
    # Note to self: by catching the errors here, we can differentiate between:
    # - error opening the file (permission issues)
    # - error parsing the file (malformed TOML)
    # - error validating the file (malformed values)

    config_dir = _get_dir_following_xdg_spec(XDGDirectory.CONFIG)
    config_file_path = config_dir / "config.toml"

    try:
        f = open(config_file_path, "r")
    except OSError as e:
        # Any kind of error trying to read this file is a breaking error.
        core.os_error_logger(e, "read", "config file")
        raise e

    try:
        config_tomldoc = tomlkit.parse(f.read())
    except tomlkit.exceptions.ParseError as e:
        e.add_note(
            f"Error parsing config file at: {config_dir} -- "
            f"Error found at line {e.line}, column {e.col}"
        )
        core.error_storage.add_error(e)
        raise e
    except tomlkit.exceptions.TOMLKitError as e:
        e.add_note(f"Error parsing config file at: {config_dir}")
        core.error_storage.add_error(e)
        raise e

    validated_config = safely_parse_TOMLDocument(config_tomldoc, UserConfig)

    # Now we can merge the validated config with the default config.
    # Any field that is not marked as valid (or notype) will be left
    # as the default value.
    merged_dict = merge_validated_config(validated_config)

    # At this point it should be validated and safe, but just in case...
    try:
        return UserConfig(**merged_dict)
    except ValidationError as e:
        e.add_note(f"Unforseen error validating config file at: {config_dir}")
        core.error_storage.add_error(e)
        raise e


def merge_validated_config(validated_config: dict[str, ConfigField]) -> dict[str, Any]:
    """Merge a dict returned from safely_parse_TOMLDocument with the
    default config dict."""

    # model_dump() converts a model instance into a dict. So tmp_dict here is
    # a dict with all the default values.
    tmp_dict: dict[str, Any] = default_config.model_dump()
    for field_name, field in validated_config.items():

        if field.status == ConfigStatus.VALID:
            tmp_dict.update({field_name: field.value})
        elif field.status in (ConfigStatus.MISSING, ConfigStatus.EMPTY, ConfigStatus.INVALID):
            pass  # Just leave as the default value
            # for INVALID, a pydantic ValidationError should have been added to the
            # error_storage by the safely_parse_TOMLDocument function.
        elif field.status == ConfigStatus.NONEXISTENT:
            # This won't affect the program, but we will still alert the user
            core.error_storage.add_error(
                ValueError(
                    f"Config field {field_name} in your config file is not used by this program."
                )
            )
        elif field.status == ConfigStatus.NOTYPE:
            # If there's no type then there's nothing to validate. Must assume
            # this is intentional.
            tmp_dict.update({field_name: field.value})
        else:
            raise RuntimeError(f"Unexpected ConfigStatus type: {field.status}")

    return tmp_dict


class ConfigField:
    """Wrapper to track both the value and its parsing status.
    Does NOT track the key."""

    def __init__(self, value: Any = None, status: ConfigStatus = ConfigStatus.MISSING):
        self.value = value
        self.status = status

    def __repr__(self) -> str:
        return f"ConfigField(value={self.value}, status={self.status.value})"


def safely_parse_TOMLDocument(
    tomldoc: tomlkit.TOMLDocument, model: type[BaseModel]
) -> dict[str, ConfigField]:
    """
    Parse tomlkit.TOMLDocument object using a provided Pydantic model. This will validate
    the TOMLDocument object against the model and return a dict, mapping field names
    to our custom ConfigField objects (in this module).

    This tracks whether each field is valid, missing, empty, or invalid. It should
    allow for partial parsing of the config file.

    Note to future self: This takes a model arg because its designed to be re-usable
    for future projects.

    Args:
        tomldoc (tomlkit.TOMLDocument): The TOMLDocument object to parse
        model (type[BaseModel]): The Pydantic model to validate against
    Returns:
        dict[str, ConfigField]: A dict mapping field names to ConfigField objects.
    """

    # Initialize result dict with default values (None, Missing)
    result = {field_name: ConfigField() for field_name in model.model_fields.keys()}

    # Initialize type adapters for each field.
    # NOTE: This is safe here because I built the model, I know the field types.
    # This might not be a safe operation if that wasn't the case.
    # For the purpose of this function, we're assuming the programmer knows the field types
    # and will be testing them in development, so there's no reason to catch errors here.
    adapters = {
        field_name: TypeAdapter(field_type.annotation)
        for field_name, field_type in model.model_fields.items()
    }

    # Process every field that exists in the TOML
    for field_name, raw_value in tomldoc.items():
        if isinstance(raw_value, tomlkit.items.Table):
            # Tables are essentially dictionaries, so we can treat them the same
            for table_field_name, table_raw_value in raw_value.items():
                if table_field_name in model.model_fields:

                    # Check if the value is empty string
                    if table_raw_value == "":
                        result[table_field_name] = ConfigField(
                            value=table_raw_value, status=ConfigStatus.EMPTY
                        )
                    else:
                        # the annotation here effectively tells us the field type.
                        # This is always `None` by default if the field doesn't have
                        # a type annotation, so its always safe to check it in this manner.
                        # NOTE: This only works for standard python objects.
                        # (ie. string, int, bool, list, dict, etc.)
                        # I should do more testing on using this with nested pydantic models.
                        if model.model_fields[table_field_name].annotation:
                            # Try to validate just this single field
                            try:
                                validated_value = adapters[table_field_name].validate_python(
                                    table_raw_value
                                )

                                result[table_field_name] = ConfigField(
                                    value=validated_value, status=ConfigStatus.VALID
                                )
                            except ValidationError as e:
                                # Field exists but failed validation (wrong type, etc)
                                core.error_storage.add_error(e)
                                result[table_field_name] = ConfigField(
                                    value=table_raw_value, status=ConfigStatus.INVALID
                                )
                        else:
                            # Field exists but has no type annotation or is not a standard python object
                            result[table_field_name] = ConfigField(
                                value=table_raw_value, status=ConfigStatus.NOTYPE
                            )
                else:
                    # Field doesn't exist in the model
                    # This is useful to give users an error about non-existent fields (ie typos)
                    result[table_field_name] = ConfigField(status=ConfigStatus.NONEXISTENT)

        else:
            # if it's not a table, it must be a top-level field.
            # For this program, I don't care about top-level fields. But future me might care.
            pass

    return result


# ===============================================


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
