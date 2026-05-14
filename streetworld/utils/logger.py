import logging
import os
import sys
from datetime import datetime
from pathlib import Path

global_logger = None
dup_filter = None


class DuplicateFilter(object):
    """
    For filtering specific messages
    """
    def __init__(self):
        self.msgs = set()

    def filter(self, record):
        """
        Determining filtering or not
        Args:
            record:

        Returns: boolean

        """
        rv = record.msg not in self.msgs
        if getattr(record, "log_once", False):
            self.add_msg(record.msg)
        return rv

    def add_msg(self, msg):
        """
        Add a msg to the filter
        Args:
            msg: message for filtering

        Returns: None

        """
        self.msgs.add(msg)

    def reset(self):
        """
        Reset the filter
        Returns: None

        """
        self.msgs.clear()


class CustomFormatter(logging.Formatter):
    grey = "\x1b[90m"
    blue = "\x1b[94m"
    yellow = "\x1b[93m"
    red = "\x1b[31m"
    reset = "\x1b[0m"
    base_format = "[%(asctime)s] %(level_title)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    def format(self, record):
        record.level_title = record.levelname.title()
        if record.levelno == logging.INFO:
            log_format = self.grey + self.base_format + self.reset
        elif record.levelno == logging.DEBUG:
            log_format = self.blue + self.base_format + self.reset
        elif record.levelno == logging.WARNING:
            log_format = self.yellow + self.base_format + self.reset
        elif record.levelno == logging.ERROR:
            log_format = self.red + self.base_format + self.reset
        else:
            log_format = self.base_format
        formatter = logging.Formatter(log_format, datefmt=self.date_format)
        return formatter.format(record)


class PlainFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(fmt=CustomFormatter.base_format, datefmt=CustomFormatter.date_format)

    def format(self, record):
        record.level_title = record.levelname.title()
        return super().format(record)


def get_logger():
    """
    Get the global logger
    Args:

    Returns: None

    """
    global global_logger
    global dup_filter
    if global_logger is None:
        dup_filter = DuplicateFilter()
        logger = logging.getLogger("Default")
        logger.propagate = False
        # create console handler with a higher log level
        ch = logging.StreamHandler()
        # create formatter and add it to the handlers
        ch.setFormatter(CustomFormatter())
        logger.addHandler(ch)
        logger.addFilter(dup_filter)
        global_logger = logger
    return global_logger


def configure_root_logger(level=logging.INFO, handler=None):
    logging.disable(logging.NOTSET)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    active_handler = handler or logging.StreamHandler()
    if handler is None:
        active_handler.setFormatter(CustomFormatter())
    active_handler.setLevel(logging.NOTSET)
    root_logger.addHandler(active_handler)
    root_logger.setLevel(level)
    return root_logger


def resolve_log_level(level_name: str) -> int:
    return getattr(logging, str(level_name).upper(), logging.INFO)


def setup_entrypoint_logging(
    level_name: str,
    log_name=None,
    enable_stderr: bool = True,
    log_dir="logs",
) -> str:
    """Configure root logging for entrypoints and write a timestamped log file."""
    resolved_level = resolve_log_level(level_name)
    if log_name is None:
        log_name = Path(sys.argv[0]).stem

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    shared_ts = os.environ.get("ONSITE_LOG_TS") or get_log_timestamp()
    os.environ["ONSITE_LOG_TS"] = shared_ts
    log_path = log_dir / f"{log_name}_{shared_ts}.logs"

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(PlainFormatter())
    root_logger = configure_root_logger(resolved_level, handler=file_handler)

    if enable_stderr:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setFormatter(CustomFormatter())
        stderr_handler.setLevel(logging.NOTSET)
        root_logger.addHandler(stderr_handler)

    return str(log_path)


def set_propagate(propagate=False):
    global global_logger
    global_logger.propagate = propagate


def set_log_level(level=logging.INFO):
    """
    Set the level of global logger
    Args:
        level: level.INFO, level.DEBUG, level.WARNING

    Returns: None

    """
    global global_logger
    if global_logger.level != level:
        global_logger.setLevel(level)


def reset_logger():
    """
    Reset the logger
    Returns: None
    """
    global dup_filter
    dup_filter.reset()


def get_log_timestamp() -> str:
    return datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
