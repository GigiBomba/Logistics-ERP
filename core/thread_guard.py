"""Thread-safety guard for tkinter/CTk operations.

Catches background-thread violations of tkinter's single-thread rule
at the call site rather than in __del__, where they become cryptic
``RuntimeError: main thread is not in main loop`` crashes.
"""
import threading
import functools
import logging

logger = logging.getLogger(__name__)

_main_thread_id = threading.main_thread().ident


def assert_main_thread(fn):
    """Decorator — raises RuntimeError if *fn* is called from a background thread.

    Apply to any method that constructs, configures, or destroys
    tkinter / CTk widgets, StringVars, IntVars, or images.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if threading.current_thread().ident != _main_thread_id:
            raise RuntimeError(
                f"THREAD VIOLATION: {fn.__qualname__} called from "
                f"thread '{threading.current_thread().name}'. "
                f"All tkinter operations must run on the main thread."
            )
        return fn(*args, **kwargs)
    return wrapper
