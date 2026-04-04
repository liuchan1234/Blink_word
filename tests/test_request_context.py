"""
Tests for app.request_context — request_id propagation via contextvars.
"""

import logging
import pytest
from app.request_context import set_request_id, get_request_id, RequestIdFilter


class TestRequestId:

    def test_set_and_get(self):
        """set_request_id should be retrievable via get_request_id."""
        rid = set_request_id(12345)
        assert rid.startswith("12345-")
        assert get_request_id() == rid

    def test_without_update_id(self):
        """Without update_id, should generate a short hex."""
        rid = set_request_id()
        assert len(rid) == 8
        assert get_request_id() == rid

    def test_each_call_generates_unique_id(self):
        """Multiple calls should produce different IDs."""
        rid1 = set_request_id(1)
        rid2 = set_request_id(2)
        assert rid1 != rid2


class TestRequestIdFilter:

    def test_filter_adds_request_id_to_record(self):
        """Log filter should inject request_id attribute."""
        set_request_id(999)
        expected_rid = get_request_id()

        f = RequestIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None,
        )
        result = f.filter(record)

        assert result is True
        assert record.request_id == expected_rid

    def test_filter_empty_when_not_set(self):
        """Before set_request_id is called, should be empty string."""
        # Reset by setting empty
        from app.request_context import _request_id_var
        _request_id_var.set("")

        f = RequestIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        f.filter(record)
        assert record.request_id == ""
