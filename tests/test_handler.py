# coding: utf-8
from __future__ import print_function, unicode_literals

import logging
import threading
import time
import unittest
from unittest.mock import patch

import mock

from clicktail import ClickHouseHandler, context
from clicktail.flush_worker import FlushWorker
from tests.env import (
    CLICKTAIL_CLICKHOUSE_DATABASE,
    CLICKTAIL_CLICKHOUSE_HOST,
    CLICKTAIL_CLICKHOUSE_TABLE,
)


class TestClickHouseHandler(unittest.TestCase):
    host = CLICKTAIL_CLICKHOUSE_HOST
    database = CLICKTAIL_CLICKHOUSE_DATABASE
    table = CLICKTAIL_CLICKHOUSE_TABLE

    @patch("clicktail.handler.FlushWorker")
    def test_handler_creates_uploader_from_args(self, mock_worker: FlushWorker) -> None:
        handler = ClickHouseHandler(
            host=self.host, database=self.database, table=self.table
        )
        expected_host = (
            self.host
            if self.host.startswith("https://") or self.host.startswith("http://")
            else "https://" + self.host
        )
        self.assertEqual(handler.uploader.host, expected_host)
        self.assertEqual(handler.uploader.database, self.database)
        self.assertEqual(handler.uploader.table, self.table)

    @patch("clicktail.handler.FlushWorker")
    def test_handler_passes_timeout_to_uploader(self, mock_worker: FlushWorker) -> None:
        # Test default timeout
        handler = ClickHouseHandler(
            host=self.host, database=self.database, table=self.table
        )
        self.assertEqual(handler.uploader.timeout, 30)

        # Test custom timeout
        handler = ClickHouseHandler(
            host=self.host, database=self.database, table=self.table, timeout=10
        )
        self.assertEqual(handler.uploader.timeout, 10)

    @patch("clicktail.handler.FlushWorker")
    def test_handler_creates_pipe_from_args(self, mock_worker: FlushWorker) -> None:
        buffer_capacity = 9
        flush_interval = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
            flush_interval=flush_interval,
        )
        self.assertTrue(handler.pipe.empty())

    @patch("clicktail.handler.FlushWorker")
    def test_handler_creates_and_starts_worker_from_args_after_first_log(
        self, mock_worker: FlushWorker
    ) -> None:
        buffer_capacity = 9
        flush_interval = 9
        check_interval = 4
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
            flush_interval=flush_interval,
            check_interval=check_interval,
        )

        self.assertFalse(mock_worker.called)

        logger = logging.getLogger(__name__)
        logger.handlers = []
        logger.addHandler(handler)
        logger.critical("hello")

        mock_worker.assert_called_with(
            handler.uploader,
            handler.pipe,
            buffer_capacity,
            flush_interval,
            check_interval,
        )
        self.assertEqual(handler.flush_thread.start.call_count, 1)

    @patch("clicktail.handler.FlushWorker")
    def test_emit_starts_thread_if_not_alive(self, mock_worker: FlushWorker) -> None:
        handler = ClickHouseHandler(
            host=self.host, database=self.database, table=self.table
        )

        logger = logging.getLogger(__name__)
        logger.handlers = []
        logger.addHandler(handler)
        logger.critical("hello")

        self.assertEqual(handler.flush_thread.start.call_count, 1)
        handler.flush_thread.is_alive = mock.Mock(return_value=False)  # type: ignore

        logger.critical("hello")

        self.assertEqual(handler.flush_thread.start.call_count, 2)

    @patch("clicktail.handler.FlushWorker")
    def test_emit_drops_records_if_configured(self, mock_worker: FlushWorker) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
            drop_extra_events=True,
        )

        logger = logging.getLogger(__name__)
        logger.handlers = []
        logger.addHandler(handler)
        logger.critical("hello")
        logger.critical("goodbye")

        log_entry = handler.pipe.get()
        self.assertEqual(log_entry["message"], "hello")
        self.assertTrue(handler.pipe.empty())
        self.assertEqual(handler.dropcount, 1)

    @patch("clicktail.handler.FlushWorker")
    def test_emit_does_not_drop_records_if_configured(
        self, mock_worker: FlushWorker
    ) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
            drop_extra_events=False,
        )

        def consumer(q):
            while True:
                if q.full():
                    while not q.empty():
                        _ = q.get(block=True)
                time.sleep(0.2)

        t = threading.Thread(target=consumer, args=(handler.pipe,))
        t.daemon = True

        logger = logging.getLogger(__name__)
        logger.handlers = []
        logger.addHandler(handler)
        logger.critical("hello")

        self.assertTrue(handler.pipe.full())
        t.start()
        logger.critical("goodbye")
        logger.critical("goodbye2")

        self.assertEqual(handler.dropcount, 0)

    @patch("clicktail.handler.FlushWorker")
    def test_error_suppression(self, mock_worker: FlushWorker) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
            raise_exceptions=True,
        )

        handler.pipe = mock.MagicMock(put=mock.Mock(side_effect=ValueError))

        logger = logging.getLogger(__name__)
        logger.handlers = []
        logger.addHandler(handler)

        with self.assertRaises(ValueError):
            logger.critical("hello")

        handler.raise_exceptions = False
        logger.critical("hello")

    @patch("clicktail.handler.FlushWorker")
    def test_can_send_unserializable_extra_data(self, mock_worker: FlushWorker) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
        )

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.handlers = []
        logger.addHandler(handler)
        logger.info("hello", extra={"data": {"unserializable": UnserializableObject()}})

        log_entry = handler.pipe.get()

        self.assertEqual(log_entry["message"], "hello")
        self.assertRegex(
            log_entry["data"]["unserializable"],
            r"^<tests\.test_handler\.UnserializableObject object at 0x[0-f]+>$",
        )
        self.assertTrue(handler.pipe.empty())

    @patch("clicktail.handler.FlushWorker")
    def test_can_send_unserializable_context(self, mock_worker: FlushWorker) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
        )

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.handlers = []
        logger.addHandler(handler)
        with context(data={"unserializable": UnserializableObject()}):
            logger.info("hello")

        log_entry = handler.pipe.get()

        self.assertEqual(log_entry["message"], "hello")
        self.assertRegex(
            log_entry["context"]["data"]["unserializable"],
            r"^<tests\.test_handler\.UnserializableObject object at 0x[0-f]+>$",
        )
        self.assertTrue(handler.pipe.empty())

    @patch("clicktail.handler.FlushWorker")
    def test_can_send_circular_dependency_in_extra_data(
        self, mock_worker: FlushWorker
    ) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
        )

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.handlers = []
        logger.addHandler(handler)
        circular_dependency = {"egg": {}}
        circular_dependency["egg"]["chicken"] = circular_dependency
        logger.info("hello", extra={"data": circular_dependency})

        log_entry = handler.pipe.get()

        self.assertEqual(log_entry["message"], "hello")
        self.assertEqual(
            log_entry["data"]["egg"]["chicken"], "<omitted circular reference>"
        )
        self.assertTrue(handler.pipe.empty())

    @patch("clicktail.handler.FlushWorker")
    def test_can_have_multiple_instance_of_same_string_in_extra_data(
        self, mock_worker: FlushWorker
    ) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
        )

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.handlers = []
        logger.addHandler(handler)
        test_string = "this is a test string"
        logger.info("hello", extra={"test1": test_string, "test2": test_string})

        log_entry = handler.pipe.get()

        self.assertEqual(log_entry["message"], "hello")
        self.assertEqual(log_entry["test1"], "this is a test string")
        self.assertEqual(log_entry["test2"], "this is a test string")
        self.assertTrue(handler.pipe.empty())

    @patch("clicktail.handler.FlushWorker")
    def test_can_have_multiple_instance_of_same_array_in_extra_data(
        self, mock_worker: FlushWorker
    ) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
        )

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.handlers = []
        logger.addHandler(handler)
        test_array = ["this is a test string"]
        logger.info("hello", extra={"test1": test_array, "test2": test_array})

        log_entry = handler.pipe.get()

        self.assertEqual(log_entry["message"], "hello")
        self.assertEqual(log_entry["test1"], ["this is a test string"])
        self.assertEqual(log_entry["test2"], ["this is a test string"])
        self.assertTrue(handler.pipe.empty())

    @patch("clicktail.handler.FlushWorker")
    def test_can_send_circular_dependency_in_context(
        self, mock_worker: FlushWorker
    ) -> None:
        buffer_capacity = 1
        handler = ClickHouseHandler(
            host=self.host,
            database=self.database,
            table=self.table,
            buffer_capacity=buffer_capacity,
        )

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.handlers = []
        logger.addHandler(handler)
        circular_dependency = {"egg": {}}
        circular_dependency["egg"]["chicken"] = circular_dependency
        with context(data=circular_dependency):
            logger.info("hello")

        log_entry = handler.pipe.get()

        self.assertEqual(log_entry["message"], "hello")
        self.assertEqual(
            log_entry["context"]["data"]["egg"]["chicken"]["egg"],
            "<omitted circular reference>",
        )
        self.assertTrue(handler.pipe.empty())


class UnserializableObject:
    """Because this is a custom class, it cannot be serialized into JSON."""
