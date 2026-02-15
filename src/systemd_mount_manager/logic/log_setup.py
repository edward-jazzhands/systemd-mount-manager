"""
Logging configuration setup with XDG support and QueueHandler/QueueListener.

This module handles loading logging configuration from a .ini file using fileConfig,
with proper XDG directory support and a queue-based handler system for thread-safe
async logging.
"""

# Standard lib imports
from pathlib import Path
from typing import Any
import logging
import logging.config
import logging.handlers
import queue
import atexit
import os

# Third party
from textual import log as textual_log

# Local imports
import systemd_mount_manager.logic.config as config_module


# Configuration constants
# =======================
APP_NAME = "systemd-mount-manager"
CONFIG_FILENAME = "logging-config.ini"

# XDG fallback for when XDG_CONFIG_HOME is not set
DEFAULT_CONFIG_DIR = Path.home() / ".config"

DEFAULT_LOGGING_CONFIG_YAML = """\
# Logging configuration
logging:
  version: 1
  disable_existing_loggers: false
  
  formatters:
    detailed:
      format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
      datefmt: "%Y-%m-%d %H:%M:%S"
    simple:
      format: "%(levelname)s - %(message)s"
  
  handlers:
    queue:
      class: logging.handlers.QueueHandler
    console:
      class: logging.StreamHandler
      formatter: simple
      stream: ext://sys.stdout
  
  root:
    level: INFO
    handlers: [queue]
"""

#! Not sure if this is needed
# class TextualLogWriter:
#     "A class to write a bunch of strings to a buffer and then run the send method."

#     def __init__(self) -> None:
#         self.buffer: list[str] = []

#     def send(self) -> None:
#         "write collected messages to terminal"

#         log_string = "".join(self.buffer)
#         log(log_string.rstrip("\n"))
#         self.buffer = []

#     def append(self, message: str) -> None:
#         self.buffer.append(message)


# # The Log Writer instance
# textual_log_writer = TextualLogWriter()
# "Write a bunch of strings to a buffer and then run the send method"



def create_default_logging_config(config_path: Path) -> None:
    """
    Create a default logging configuration file with QueueHandler setup.

    This creates a config that uses QueueHandler as the primary handler,
    which will be swapped for real handlers via QueueListener.

    Args:
        config_path: Path where config file should be written
    """

    config_path.write_text(DEFAULT_LOGGING_CONFIG)


def setup_queue_handlers(
    log_queue: queue.Queue[logging.LogRecord], real_handlers: list[logging.Handler]
) -> tuple[logging.Handler, logging.handlers.QueueListener]:
    """
    Create QueueHandler and QueueListener for async logging.

    The QueueHandler goes on loggers (producer side), and the QueueListener
    manages the real handlers that do the actual work (consumer side).

    Why queue-based? Thread-safe, non-blocking logging. Loggers just push
    to queue and return immediately. Background thread pulls from queue and
    handles actual I/O/formatting.

    Args:
        log_queue: Queue for passing log records
        real_handlers: Actual handlers (FileHandler, etc.) that process logs

    Returns:
        Tuple of (QueueHandler, QueueListener)
    """
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # QueueListener runs in background thread, pulls from queue, dispatches to real handlers
    # respect_handler_level=True ensures handler-level filtering still works
    listener = logging.handlers.QueueListener(log_queue, *real_handlers, respect_handler_level=True)

    return queue_handler, listener


def create_real_handlers() -> list[logging.Handler]:
    """
    Create the actual handlers that will process log records.

    These are managed by QueueListener, not attached to loggers directly.
    Add/customize handlers here based on your needs.

    Returns:
        List of configured handlers
    """
    handlers = []

    # Console handler with simple formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    # File handler with detailed formatting
    # You might want to make this path configurable too
    log_dir = config_module.ensure_config_dir(APP_NAME)
    log_file = log_dir / f"{APP_NAME}.log"

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(detailed_formatter)
    handlers.append(file_handler)

    return handlers


def setup_logging(app_name: str = APP_NAME, config_filename: str = CONFIG_FILENAME) -> None:
    """
    Setup logging with fileConfig and queue-based handler system.

    Handles:
    - Finding/creating config file in XDG-compliant location
    - Loading base config with fileConfig
    - Replacing placeholder handler with QueueHandler
    - Setting up QueueListener with real handlers
    - Ensuring listener shutdown on program exit

    Args:
        app_name: Application name for config directory
        config_filename: Name of logging config file
    """
    # Find or create config file
    config_path = config_module.find_config_file(app_name, config_filename)

    if config_path is None:
        # No config exists, create default
        config_dir = config_module.ensure_config_dir(app_name)
        config_path = config_dir / config_filename
        create_default_logging_config(config_path)

    # Load the config file using fileConfig
    # This creates all loggers/handlers/formatters defined in the .ini file
    # disable_existing_loggers=False preserves any loggers already created
    logging.config.fileConfig(config_path, disable_existing_loggers=False)

    # Now replace the handlers with our queue system
    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(-1)  # Unlimited queue
    real_handlers = create_real_handlers()
    queue_handler, listener = setup_queue_handlers(log_queue, real_handlers)

    # Replace all handlers on root logger with just the QueueHandler
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(queue_handler)

    # Start the listener (background thread starts consuming from queue)
    listener.start()

    # Ensure listener stops cleanly on program exit
    # This flushes remaining queue items and closes handlers
    atexit.register(listener.stop)


# Example usage for other config files
def load_app_config(app_name: str, config_filename: str) -> Any:
    """
    Generic config file loader (example for other config files).

    This shows how to reuse the XDG path logic for other config files.

    Args:
        app_name: Application name
        config_filename: Config file to load

    Returns:
        Parsed config (adjust return type based on parser used)
    """
    from configparser import ConfigParser

    config_path = config_module.find_config_file(app_name, config_filename)

    if config_path is None:
        # Handle missing config - could create default, raise error, etc.
        config_dir = config_module.ensure_config_dir(app_name)
        config_path = config_dir / config_filename
        # Create default config here...

    parser = ConfigParser()
    # read() can fail if file is malformed
    try:
        parser.read(config_path)
    except Exception as e:
        # Log error (if logging is set up) and potentially fall back to defaults
        logging.error(f"Failed to parse config file {config_path}: {e}")
        raise

    return parser


if __name__ == "__main__":
    # Example setup
    setup_logging()

    # Test it
    logger = logging.getLogger(__name__)
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
