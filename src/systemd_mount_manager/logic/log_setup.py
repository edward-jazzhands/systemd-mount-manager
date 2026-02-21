# standard lib
import logging
import logging.handlers as handlers
import queue
import atexit
from dataclasses import dataclass
import copy
import time
import json
import struct
import multiprocessing

# import time
# from threading import Thread

# third party
# from textual.logging import TextualHandler

# local imports
import systemd_mount_manager.logic.core as core

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

# Set the app name in multiprocessing module.
# Logging library uses this under the hood to set the processName
# attribute of the LogRecord object. It seems odd, but that's how it
# does it, so multiprocessing is already loaded into memory if you're
# using the logging library.
multiprocessing.current_process().name = core.APP_NAME


# Custom Handlers
# ==================

class CustomMemoryHandler(logging.Handler):

    def __init__(self):
        super().__init__()
        self.log_list: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.log_list.append(record)

    def get_log_list_copy(self) -> list[logging.LogRecord]:
        return copy.deepcopy(self.log_list)

    def flush(self) -> None:
        self.acquire()
        try:
            self.log_list.clear()
        finally:
            self.release()


class JsonSocketHandler(handlers.SocketHandler):

    def __init__(self, host: str = "localhost", port: int | None = handlers.DEFAULT_TCP_LOGGING_PORT):
        """Initializes the handler with a specific host address and port. Default host
        is 'localhost' and default port is 9020.

        When the attribute *closeOnError* is set to True - if a socket error
        occurs, the socket is silently closed and then reopened on the next
        logging call.
        """
        super().__init__(host, port)

    # The original method is called makePickle. We need to override it.
    # We are not actually pickling the object though, we're converting it
    # to a dictionary and then encoding it to JSON.
    def makePickle(self, record):
        
        # Convert the LogRecord to a dictionary
        data = record.__dict__.copy()
        
        # 2. Handle the Exception/Traceback safely
        if record.exc_info:
            # If the record has an exception, we use the formatter to 
            # turn the traceback object into a JSON-friendly string.
            formatter = self.formatter if self.formatter else logging.Formatter()

            data['exc_info'] = formatter.formatException(record.exc_info)
            
        # 3. Clean up other non-serializable fields (optional but safe)
        # Some records contain objects that JSON hates. We ensure 'msg' is a string.
        data['msg'] = record.getMessage()

        # 4. Remove args from the dictionary (optional but safe)
        # We want to remove args because once getMessage() has been, called the args 
        # are already baked into msg, so they're redundant and potentially 
        # carry non-serializable objects.
        data.pop('args', None)
            
        # Encode to JSON and then to bytes
        s = json.dumps(data).encode('utf-8')
        
        # Prefix with 4-byte length (Big-Endian) just like the original
        return struct.pack(">L", len(s)) + s


# Module level cache
# ==================
@dataclass(frozen=True)
class HandlerStorage:
    """Creates an immutable dataclass that serves as in-memory storage for the
    intialized logging handlers."""

    file_handler: handlers.TimedRotatingFileHandler | None = None
    memory_handler: CustomMemoryHandler | None = None
    socket_handler: handlers.SocketHandler | None = None
    queue_handler: handlers.QueueHandler | None = None


_handler_storage = HandlerStorage()
"""Logging handler storage. For internal use in logging module."""

# First get root logger (we specifically want root logger)
logger = logging.getLogger()
"Global root logger instance. Import this into other modules."


def _create_file_handler_safely() -> handlers.TimedRotatingFileHandler | None:
    """ """

    logs_dir = core._get_dir_following_xdg_spec(core.XDGDirectory.STATE)

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # NOTE: If there was an error here, the logger won't be ready yet (because
        # we are setting up logging right now). So we have to remember to handle it later.
        core.os_error_logger(e, "create", "logs directory")
        return
    try:
        file_handler = handlers.TimedRotatingFileHandler(
            f"{logs_dir}/{core.APP_NAME}.log", when="midnight", interval=1, backupCount=7
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

    #! potential config options:
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

    # The memory handler stores all log records in memory.
    memory_handler = CustomMemoryHandler()
    # Memory handler doesn't use a formatter.

    # The file handler is not added until the program has tried to read the config file.
    # But it will still attempt to create the file on this operation:
    if file_handler := _create_file_handler_safely():
        formatter_files = logging.Formatter(
            "%(asctime)s - %(threadName)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter_files)

    # Textual handler sends to the Textual dev console (in Textual dev tools).
    # We only add it if we're in dev mode.
    # textual_handler = None
    socket_handler = None
    if dev_mode:
        # textual_handler = TextualHandler(stderr=True)
        socket_handler = JsonSocketHandler()
        formatter_dev_consoles = logging.Formatter("%(message)s")
        # textual_handler.setFormatter(formatter_dev_consoles)
        socket_handler.setFormatter(formatter_dev_consoles)


    # The queue handler is the ONLY handler added to the root logger!
    # queue handler does not use a formatter.
    queue_handler = handlers.QueueHandler(log_queue)

    # Add all handlers to the module storage
    global _handler_storage
    _handler_storage = HandlerStorage(
        file_handler,
        memory_handler,
        socket_handler,
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
    if socket_handler:
        handlers_list.append(socket_handler)

    listener = handlers.QueueListener(log_queue, *handlers_list, respect_handler_level=True)

    # Start the listener thread
    listener.start()

    # === Add QueueHandler to Root Logger === #
    logger.addHandler(queue_handler)

    # Clean up - stop the listener to flush remaining records
    atexit.register(listener.stop)

    # Add the logger to the error storage
    core.error_storage.add_logger(logger)

    # If there was any errors during the logging setup (ie. file handler),
    # we can log them now.
    for err in core.error_storage.get_list_copy():
        logger.error(str(err))

    # if the file handler failed to initialize, we will consider that a failure.
    # Note that we still want the logger initialized with the QueueHandler and
    # whatever other handlers are available.
    if file_handler is None:
        return False
    else:
        return True


def add_file_handler_to_logger() -> bool:
    """Add the file handler to the logger. If there is no file handler
    to add, this will do nothing and then return False.
    
    Returns:
        bool: True if the swap was successful, False if it failed.
    """

    # This will only be allowed if the file handler was initialized successfully.
    if _handler_storage.file_handler:
        logger.addHandler(_handler_storage.file_handler)

        # Now we need to check for any logs that were stored in the memory handler.
        # This should effectively catch up the file handler to the latest log.
        if _handler_storage.memory_handler:
            for log in _handler_storage.memory_handler.get_log_list_copy():
                _handler_storage.file_handler.handle(log)
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