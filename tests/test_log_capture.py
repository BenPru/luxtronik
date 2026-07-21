"""Tests for custom_components.luxtronik2.log_capture."""

from __future__ import annotations

import logging
from unittest.mock import patch

from custom_components.luxtronik2 import log_capture
from custom_components.luxtronik2.const import LOGGER
from custom_components.luxtronik2.log_capture import _RingBufferLogHandler


def _make_record(message: str, level: int = logging.DEBUG) -> logging.LogRecord:
    return logging.LogRecord(
        name="custom_components.luxtronik2",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


class TestRingBufferLogHandler:
    def test_keeps_most_recent_within_maxlen(self):
        handler = _RingBufferLogHandler(maxlen=3)
        for i in range(5):
            handler.emit(_make_record(f"msg-{i}"))

        records = handler.get_records()

        assert len(records) == 3
        assert "msg-2" in records[0]
        assert "msg-3" in records[1]
        assert "msg-4" in records[2]

    def test_format_includes_level_and_logger_name_and_message(self):
        handler = _RingBufferLogHandler(maxlen=10)
        handler.emit(_make_record("hello world", level=logging.WARNING))

        [record] = handler.get_records()

        assert "WARNING" in record
        assert "custom_components.luxtronik2" in record
        assert "hello world" in record

    def test_emit_falls_back_to_raw_message_on_formatting_error(self):
        handler = _RingBufferLogHandler(maxlen=10)
        with patch.object(handler, "format", side_effect=ValueError("boom")):
            handler.emit(_make_record("raw fallback message"))

        [record] = handler.get_records()
        assert record == "raw fallback message"

    def test_empty_when_nothing_emitted(self):
        handler = _RingBufferLogHandler(maxlen=10)
        assert handler.get_records() == []


class TestGetCapturedLogRecords:
    def test_handler_is_attached_to_the_shared_logger(self):
        handler = log_capture._get_handler()
        assert handler in LOGGER.handlers

    def test_get_handler_returns_the_same_instance(self):
        assert log_capture._get_handler() is log_capture._get_handler()

    def test_captures_records_logged_through_the_shared_logger(self):
        previous_level = LOGGER.level
        LOGGER.setLevel(logging.DEBUG)
        try:
            marker = "unique-test-marker-log-capture-xyz"
            LOGGER.debug(marker)
            records = log_capture.get_captured_log_records()
        finally:
            LOGGER.setLevel(previous_level)

        assert any(marker in record for record in records)
