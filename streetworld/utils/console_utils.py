"""
Simplified console utilities for StreetWorld.
Extracted and simplified from EasyDrive's console_utils module.
"""

import os
import sys
from contextlib import contextmanager

# Try to import rich for better console output
try:
    from rich.console import Console
    from rich.text import Text
    from rich.style import Style

    console = Console(soft_wrap=True, tab_size=4)

    def _log_with_rich(*stuff, **kwargs):
        """Log using rich console."""
        console.log(*stuff, **kwargs)

    def _markup_to_ansi(string: str) -> str:
        """Convert rich-style markup to ANSI sequences."""
        with console.capture() as out:
            console.print(string, soft_wrap=True)
        return out.get()

except ImportError:
    # Fallback to basic print if rich is not available
    console = None

    def _log_with_rich(*stuff, **kwargs):
        """Log using basic print."""
        print(*stuff)

    def _markup_to_ansi(string: str) -> str:
        """Return string as-is if rich is not available."""
        return string


def log(*stuff, **kwargs):
    """
    Perform logging using the console.

    Args:
        *stuff: Items to log
        **kwargs: Additional keyword arguments
    """
    _log_with_rich(*stuff, **kwargs)


@contextmanager
def suppress_process_output():
    sys.stdout.flush()
    sys.stderr.flush()

    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    stdout_fd = os.dup(1)
    stderr_fd = os.dup(2)
    try:
        os.dup2(devnull_fd, 1)
        os.dup2(devnull_fd, 2)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)
        os.close(stdout_fd)
        os.close(stderr_fd)
        os.close(devnull_fd)


# Color functions using rich markup
def red(string: str) -> str:
    """Format string in red bold."""
    return f"[red bold]{string}[/]"


def blue(string: str) -> str:
    """Format string in blue bold."""
    return f"[blue bold]{string}[/]"


def cyan(string: str) -> str:
    """Format string in cyan bold."""
    return f"[cyan bold]{string}[/]"


def pink(string: str) -> str:
    """Format string in pink (bright magenta) bold."""
    return f"[bright_magenta bold]{string}[/]"


def green(string: str) -> str:
    """Format string in green bold."""
    return f"[green bold]{string}[/]"


def yellow(string: str) -> str:
    """Format string in yellow bold."""
    return f"[yellow bold]{string}[/]"


def magenta(string: str) -> str:
    """Format string in magenta bold."""
    return f"[magenta bold]{string}[/]"


# Export all functions for `from console_utils import *`
__all__ = [
    'log',
    'suppress_process_output',
    'red',
    'blue',
    'cyan',
    'pink',
    'green',
    'yellow',
    'magenta',
    'console',
]
