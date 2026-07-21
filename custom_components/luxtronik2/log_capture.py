"""In-memory ring buffer of this integration's own log records.

Diagnostics (`diagnostics.py`) embeds these alongside the parameter/
calculation/visibility dump, so a single "Download diagnostics" action
captures both state and recent log activity - no more asking a bug
reporter to separately enable debug logging, reproduce, and download a
second file from the system log.

The buffer only ever contains records the user's own logging configuration
already allowed through (typically nothing below INFO unless the user
enabled debug logging for this integration first) - this module doesn't
change what gets logged, only keeps a copy of it in memory.
"""

from __future__ import annotations

from collections import deque
import logging
import threading

from .const import LOGGER, MAX_CAPTURED_LOG_RECORDS

_FORMATTER = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")


class _RingBufferLogHandler(logging.Handler):
    """Keeps the most recent formatted log records in memory.

    A `deque(maxlen=...)` already discards the oldest entry once full, so
    no separate trimming logic is needed. `emit()` can run on any thread
    (the luxtronik client's blocking calls run in HA's executor), so a lock
    guards the deque against concurrent reads from `get_records()`.
    """

    def __init__(self, maxlen: int) -> None:
        super().__init__(level=logging.NOTSET)
        self._records: deque[str] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self.setFormatter(_FORMATTER)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - formatting itself should not fail
            message = record.getMessage()
        with self._lock:
            self._records.append(message)

    def get_records(self) -> list[str]:
        with self._lock:
            return list(self._records)


_handler: _RingBufferLogHandler | None = None


def _get_handler() -> _RingBufferLogHandler:
    """Return the shared handler, attaching it to LOGGER on first use.

    Guarded the same way as `_OVERRIDES_APPLIED` in coordinator.py - this
    must attach exactly once per process, not once per config entry, since
    HA can load multiple Luxtronik devices that all log through the same
    package-level LOGGER.
    """
    global _handler
    if _handler is None:
        _handler = _RingBufferLogHandler(MAX_CAPTURED_LOG_RECORDS)
        LOGGER.addHandler(_handler)
    return _handler


def get_captured_log_records() -> list[str]:
    """Return the most recent log records emitted by this integration."""
    return _get_handler().get_records()


# Attaching on import - rather than waiting for the first
# `get_captured_log_records()` call from diagnostics - means records are
# captured from the earliest possible point in this integration's setup,
# including startup-time failures that only ever happen once, right after
# a restart with debug logging already enabled.
_get_handler()
