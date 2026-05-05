# coding: utf-8
from __future__ import print_function, unicode_literals

import queue
import sys
import threading
import time
import unittest
from typing import Callable
from unittest.mock import patch

import mock

from clicktail.flush_worker import FlushWorker
from clicktail.uploader import Uploader, UploadResponse
from tests.env import (
    CLICKTAIL_CLICKHOUSE_DATABASE,
    CLICKTAIL_CLICKHOUSE_HOST,
    CLICKTAIL_CLICKHOUSE_PAYLOAD_COLUMN,
    CLICKTAIL_CLICKHOUSE_TABLE,
)


class TestFlushWorker(unittest.TestCase):
    host = CLICKTAIL_CLICKHOUSE_HOST
    database = CLICKTAIL_CLICKHOUSE_DATABASE
    table = CLICKTAIL_CLICKHOUSE_TABLE
    payload_column = CLICKTAIL_CLICKHOUSE_PAYLOAD_COLUMN
    buffer_capacity = 5
    flush_interval = 2.0
    check_interval = 0.01
    timeout = 0.1

    def _setup_worker(
        self, uploader: Uploader | Callable | None = None
    ) -> tuple[queue.Queue, Uploader | Callable, FlushWorker]:
        pipe = queue.Queue(maxsize=self.buffer_capacity)
        uploader = uploader or Uploader(
            self.host,
            self.database,
            self.table,
            None,
            None,
            None,
            self.payload_column,
            self.timeout,
        )
        fw = FlushWorker(
            uploader,
            pipe,
            self.buffer_capacity,
            self.flush_interval,
            self.check_interval,
        )
        return pipe, uploader, fw

    def test_is_thread(self) -> None:
        _, _, fw = self._setup_worker()
        self.assertIsInstance(fw, threading.Thread)

    def test_flushes_when_queue_is_full(self) -> None:
        first_frame = list(range(self.buffer_capacity))
        self.calls = 0
        self.flush_interval = 1000

        def uploader(frame: list[dict]) -> None:
            self.calls += 1
            self.assertEqual(frame, first_frame)
            return mock.MagicMock(status_code=202)

        pipe, _, fw = self._setup_worker(uploader)

        for log in first_frame:
            pipe.put(log, block=False)

        t1 = time.time()
        fw.step()
        t2 = time.time()
        self.assertLess(t2 - t1, self.flush_interval)

        self.assertEqual(self.calls, 1)

    @patch("clicktail.flush_worker._calculate_time_remaining")
    def test_flushes_after_interval(self, calculate_time_remaining: bool) -> None:
        self.buffer_capacity = 10
        num_items = 2
        first_frame = list(range(self.buffer_capacity))
        self.assertLess(num_items, self.buffer_capacity)

        self.upload_calls = 0

        def uploader(frame):
            self.upload_calls += 1
            self.assertEqual(frame, first_frame[:num_items])
            return mock.MagicMock(status_code=202)

        self.timeout_calls = 0

        def timeout(last_flush: float, interval: float) -> float:
            self.timeout_calls += 1
            # Until the last item has been retrieved from the pipe, the timeout
            # length doesn't matter. After the last item has been retrieved,
            # return a very small number so that the blocking get times out
            if self.timeout_calls < num_items:
                return 1000000.0
            return 0.0

        calculate_time_remaining.side_effect = timeout

        pipe, _, fw = self._setup_worker(uploader)
        for i in range(num_items):
            pipe.put(first_frame[i], block=False)

        fw.step()
        self.assertEqual(self.upload_calls, 1)
        self.assertEqual(self.timeout_calls, 2)

    @patch("clicktail.flush_worker._calculate_time_remaining")
    @patch("clicktail.flush_worker._initial_time_remaining")
    def test_does_nothing_without_any_items(
        self, initial_time_remaining: float, calculate_time_remaining: float
    ) -> None:
        calculate_time_remaining.side_effect = lambda a, b: 0.0
        initial_time_remaining.side_effect = lambda a: 0.0001

        uploader = mock.MagicMock(side_effect=mock.MagicMock(status_code=202))
        pipe, _, fw = self._setup_worker(uploader)

        self.assertEqual(pipe.qsize(), 0)
        fw.step()
        self.assertFalse(uploader.called)

    @patch("clicktail.flush_worker.time.sleep")
    def test_retries_according_to_schedule(self, mock_sleep: mock.MagicMock) -> None:
        first_frame = list(range(self.buffer_capacity))

        self.uploader_calls = 0

        def uploader(frame):
            self.uploader_calls += 1
            self.assertEqual(frame, first_frame)
            return mock.MagicMock(status_code=500)

        self.sleep_calls = 0

        def sleep(time: float) -> None:
            self.assertEqual(time, FlushWorker.RETRY_SCHEDULE[self.sleep_calls])
            self.sleep_calls += 1

        mock_sleep.side_effect = sleep

        pipe, _, fw = self._setup_worker(uploader)

        for log in first_frame:
            pipe.put(log, block=False)

        fw.step()
        self.assertEqual(self.uploader_calls, len(FlushWorker.RETRY_SCHEDULE) + 1)
        self.assertEqual(self.sleep_calls, len(FlushWorker.RETRY_SCHEDULE))

    def test_shutdown_condition_empties_queue_and_shuts_down(self) -> None:
        self.buffer_capacity = 10
        num_items = 5
        first_frame = list(range(self.buffer_capacity))
        self.assertLess(num_items, self.buffer_capacity)

        self.upload_calls = 0

        def uploader(frame: dict) -> UploadResponse:
            self.upload_calls += 1
            self.assertEqual(frame, first_frame[:num_items])
            return mock.MagicMock(status_code=202)  # type: ignore

        pipe, _, fw = self._setup_worker(uploader)
        fw.parent_thread = mock.MagicMock(is_alive=lambda: False)

        for i in range(num_items):
            pipe.put(first_frame[i], block=False)

        fw.step()
        self.assertEqual(self.upload_calls, 1)
        self.assertFalse(fw.should_run)

    # test relies on overriding excepthook which is available from 3.8+
    @unittest.skipIf(
        sys.version_info < (3, 8),
        "Test skipped because overriding excepthook is only available on Python 3.8+",
    )
    def test_shutdown_dont_raise_exception_in_thread(self) -> None:
        original_excepthook = threading.excepthook
        threading.excepthook = mock.Mock()

        _, _, fw = self._setup_worker()
        fw.parent_thread = mock.MagicMock(is_alive=lambda: False)
        fw.step()

        self.assertFalse(fw.should_run)
        self.assertFalse(threading.excepthook.called)

        threading.excepthook = original_excepthook
