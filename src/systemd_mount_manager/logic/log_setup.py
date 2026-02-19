# standard lib
import logging
import logging.handlers as handlers
import queue
import atexit
from dataclasses import dataclass

# import time
# from threading import Thread

# third party
from textual.logging import TextualHandler

# local imports
import systemd_mount_manager.logic.core as core
import systemd_mount_manager.logic.config as config

APP_NAME = core.APP_NAME

#! we need to set up a flag somewhere that we can use to know
# the result of the config startup


# This module is loaded before the config startup function is called, because
# we want logging to be able to keep track of config errors.
# So the config storage will only have the default config loaded at this point.

# Note that the user's logs directory might change after the program starts. But
# until we have parsed and confirmed that, we have to use the default directory
# (or the XDG_STATE_HOME env var if the user has it set).
# The program will avoid writing any log files until it has attempted to read
# the config file. If it tries and fails to get a valid entry for the logs dir,
# then it will fall back to the default dir, and write the log buffer to a file.

# == Priority ==
# 1. User config file
# 2. XDG_STATE_HOME env var
# 3. ~/.local/state


class CustomMemoryHandler(handlers.MemoryHandler):

    def __init__(self, target: logging.Handler):
        super().__init__(capacity=10, flushLevel=logging.ERROR, target=target, flushOnClose=True)

        # NOTE: If the target is None, it will never flush the buffer.
        # The buffer is just a list, but it could end up making the list
        # grow very large, and that might not be great for performance.

    def shouldFlush(self, record: logging.LogRecord) -> bool:

        # NOTE: this method will run in a different thread because its called
        # by the QueueListener! So that's why we need to worry about thread safety.
        # (QueueListener thread calls handle -> handle calls emit -> emit calls shouldFlush)

        # We can't flush until the program has attempted to read the config file.
        # Once that happens we can start flushing the buffer to the file handler.
        if not config.config_storage.parsing_stage_completed:
            return False

        return (len(self.buffer) >= self.capacity) or (record.levelno >= self.flushLevel)


# Module level cache
# ==================
@dataclass(frozen=True)
class HandlerStorage:
    """Creates an immutable dataclass that serves as in-memory storage for the
    intialized logging handlers."""

    file_handler: handlers.TimedRotatingFileHandler | None = None
    memory_handler: CustomMemoryHandler | None = None
    textual_handler: TextualHandler | None = None
    queue_handler: handlers.QueueHandler | None = None


_handler_storage = HandlerStorage()
"""Logging handler storage. For internal use in logging module."""

# First get root logger (we specifically want root logger)
logger = logging.getLogger()
"Global root logger instance. Import this into other modules."


def _create_file_handler_safely() -> handlers.TimedRotatingFileHandler | None:
    """ """

    logs_dir = config._get_dir_following_xdg_spec(config.XDGDirectory.STATE)

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # NOTE: If there was an error here, the logger won't be ready yet (because
        # we are setting up logging right now). So we have to remember to handle it later.
        core.os_error_logger(e, "create", "logs directory")
        return
    try:
        file_handler = handlers.TimedRotatingFileHandler(
            f"{logs_dir}/{APP_NAME}.log", when="midnight", interval=1, backupCount=7
        )
        # valid 'when' events:
        # S - Seconds
        # M - Minutes
        # H - Hours
        # D - Days
        # midnight - roll over at midnight
        # W{0-6} - roll over on a certain day; 0 - Monday
        #
        # lower or upper case will work.

    except OSError as e:
        core.os_error_logger(e, "creating or accessing", "log file")
        return

    return file_handler

    # potential config options:
    # backup count (it goes by day so its how many days to keep - default is 1 week)
    # daily / weekly


def startup_logging() -> bool:
    """Program startup logic API for the logging module

    Returns:
        bool: True if logging startup was sucessful, False if there was an error.
    Raises:
        Nothing. Should catch errors without raising.
    """

    logger.setLevel(logging.DEBUG)

    dev_mode = core.check_dev_env_var()

    # Create a queue for log records
    log_queue: queue.Queue[logging.LogRecord] = queue.Queue()

    # === Logging Handlers === #

    # Note to future self: Adding new logging integrations should be as simple as
    # importing the handler from some third party library and adding it to the logger.

    # The file handler is not added until the program has tried to read the config file.
    # But it will still attempt to create the file on this operation:
    memory_handler = None
    if file_handler := _create_file_handler_safely():

        # The memory handler stores records in memory and periodically flushes
        # them to the file handler. There's no point in initializing it if
        # the file handler failed to initialize.
        memory_handler = CustomMemoryHandler(target=file_handler)
        # Memory handler doesn't use a formatter.
        
        formatter_files = logging.Formatter(
            "%(asctime)s - %(threadName)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter_files)

    # Textual handler sends to the Textual dev console (in Textual dev tools).
    # We only add it if we're in dev mode.
    textual_handler = None
    if dev_mode:
        textual_handler = TextualHandler(stderr=False)
        
        formatter_textual = logging.Formatter("%(message)s")
        textual_handler.setFormatter(formatter_textual)

    # The queue handler is the ONLY handler added to the root logger!
    # queue handler does not use a formatter.
    queue_handler = handlers.QueueHandler(log_queue)

    # Add all handlers to the module storage
    global _handler_storage
    _handler_storage = HandlerStorage(
        file_handler,
        memory_handler,
        textual_handler,
        queue_handler,
    )

    # === Queue Listener === #

    # Create the listener that will process records from the queue.
    # The listener starts up a separate thread to process records. The python
    # Queue class uses a threading.Condition object which has a wait() method.
    # If the queue is empty, this method puts the thread to sleep until a new item
    # is added, so its very efficient on CPU while waiting for new items to arrive.

    handlers_list: list[logging.Handler] = []
    if memory_handler:
        handlers_list.append(memory_handler)
    if textual_handler:
        handlers_list.append(textual_handler)

    listener = handlers.QueueListener(log_queue, *handlers_list, respect_handler_level=True)

    # Start the listener thread
    listener.start()

    # === Add QueueHandler to Root Logger === #
    logger.addHandler(queue_handler)

    # Clean up - stop the listener to flush remaining records
    atexit.register(listener.stop)

    # Mark the logger as ready for the error storage
    core.error_storage.logger = logger

    # If there was any errors during the logging setup (ie. file handler),
    # we can log them now.
    for err in core.error_storage.get_list_copy():
        logger.error(str(err))

    # if the file handler failed to initialize, we will consider that a failure.
    # Note that we still want the logger initialized with the QueueHandler, even
    # if the QueueListener doesn't have any handlers to send the logs to.
    if file_handler is None:
        return False
    else:
        return True


def swap_memory_handler_with_file_handler() -> bool:
    """Swap the memory handler with the file handler. If there is no file handler
    to swap in, this will do nothing and then return False.
    
    Returns:
        bool: True if the swap was successful, False if it failed.
    """

    # This will only be allowed if the file handler was initialized successfully.
    if _handler_storage.file_handler:
        logger.addHandler(_handler_storage.file_handler)
        if _handler_storage.memory_handler:  # logically this should never be None here
            logger.removeHandler(_handler_storage.memory_handler)   
        return True
    else:
        return False


def remove_memory_handler_from_logger() -> bool:
    """Remove the MemoryHandler from the root logger. If there is no MemoryHandler,
    (for example it was not initialized because the file handler had a problem),
    this will do nothing and then return False.

    Returns:
        bool: True if the MemoryHandler was removed successfully, False if it failed.
    """

    if _handler_storage.memory_handler in logger.handlers:
        logger.removeHandler(_handler_storage.memory_handler)
        return True
    else:
        return False