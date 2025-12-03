import logging
from rich.console import Console

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


class RichLogger:
    """Wrapper for rich Console with logging-like interface"""

    def __init__(self, console=None):
        self.console = console or Console()
        self._level = logging.INFO
        self.dup_filter = DuplicateFilter()

    def setLevel(self, level):
        """Set the logging level"""
        self._level = level

    def addFilter(self, filter_obj):
        """Add a filter (for compatibility)"""
        if isinstance(filter_obj, DuplicateFilter):
            self.dup_filter = filter_obj

    @property
    def level(self):
        """Get current level"""
        return self._level

    def _should_log(self, record):
        """Check if message should be logged"""
        return self.dup_filter.filter(record) if hasattr(record, "log_once") else True

    def debug(self, msg, *args, **kwargs):
        """Log debug message"""
        if self._level <= logging.DEBUG:
            self.console.print(f"[DEBUG] {msg}", style="dim")

    def info(self, msg, *args, **kwargs):
        """Log info message"""
        if self._level <= logging.INFO:
            self.console.print(f"[INFO] {msg}")

    def warning(self, msg, *args, **kwargs):
        """Log warning message"""
        if self._level <= logging.WARNING:
            self.console.print(f"[WARNING] {msg}", style="yellow")

    def error(self, msg, *args, **kwargs):
        """Log error message"""
        if self._level <= logging.ERROR:
            self.console.print(f"[ERROR] {msg}", style="red")

    def critical(self, msg, *args, **kwargs):
        """Log critical message"""
        if self._level <= logging.CRITICAL:
            self.console.print(f"[CRITICAL] {msg}", style="bold red")


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
        console = Console()
        logger = RichLogger(console)
        logger.addFilter(dup_filter)
        global_logger = logger
    return global_logger


def set_propagate(propagate=False):
    """Set propagation (for compatibility, no-op with rich)"""
    pass


def set_log_level(level=logging.INFO):
    """
    Set the level of global logger
    Args:
        level: level.INFO, level.DEBUG, level.WARNING

    Returns: None

    """
    global global_logger
    if global_logger and global_logger.level != level:
        global_logger.setLevel(level)


def reset_logger():
    """
    Reset the logger
    Returns: None
    """
    global dup_filter
    if dup_filter:
        dup_filter.reset()
