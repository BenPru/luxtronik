"""Debounce help module."""

from threading import Timer
from typing import Any, Callable


def debounce(wait: int):
    """Debounce main method."""

    def decorator(fn: Callable):
        def debounced(*args: Any, **kwargs: Any):
            def call_it() -> None:
                fn(*args, **kwargs)

            try:
                debounced.timer.cancel()
            except AttributeError:
                pass
            debounced.timer = Timer(wait, call_it)
            debounced.timer.start()

        return debounced

    return decorator
