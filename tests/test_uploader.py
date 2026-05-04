# coding: utf-8
from __future__ import print_function, unicode_literals

import json
import unittest
from unittest.mock import patch

from clicktail.uploader import Uploader
from tests.env import (
    CLICKTAIL_CLICKHOUSE_DATABASE,
    CLICKTAIL_CLICKHOUSE_HOST,
    CLICKTAIL_CLICKHOUSE_PASSWORD,
    CLICKTAIL_CLICKHOUSE_PAYLOAD_COLUMN,
    CLICKTAIL_CLICKHOUSE_TABLE,
    CLICKTAIL_CLICKHOUSE_USERNAME,
)


class TestUploader(unittest.TestCase):
    host = CLICKTAIL_CLICKHOUSE_HOST
    database = CLICKTAIL_CLICKHOUSE_DATABASE
    table = CLICKTAIL_CLICKHOUSE_TABLE
    username = CLICKTAIL_CLICKHOUSE_USERNAME
    password = CLICKTAIL_CLICKHOUSE_PASSWORD
    payload_column = CLICKTAIL_CLICKHOUSE_PAYLOAD_COLUMN
    frame = [
        {
            "dt": "2026-05-04T10:11:12.123000+00:00",
            "level": "info",
            "severity": 2,
            "message": "hello",
            "context": {"runtime": {"logger_name": "test"}},
            "request_id": "abc",
        }
    ]
    timeout = 30

    @patch("clicktail.uploader.requests.Session.post")
    def test_call(self, post):
        def mock_post(
            endpoint, data=None, headers=None, params=None, auth=None, timeout=None
        ):
            # Check that the data is sent to ther correct endpoint
            self.assertEqual(endpoint, self.host)
            self.assertEqual(
                params["query"],
                'INSERT INTO "{}"."{}" FORMAT JSONEachRow'.format(
                    self.database, self.table
                ),
            )
            self.assertEqual(auth, (self.username, self.password))
            self.assertIsInstance(headers, dict)
            self.assertEqual("application/x-ndjson", headers.get("Content-Type"))
            line = json.loads(data)
            self.assertEqual(line["dt"], "2026-05-04 10:11:12.123")
            self.assertEqual(line["message"], "hello")
            self.assertEqual(
                line[self.payload_column]["context"],
                {"runtime": {"logger_name": "test"}},
            )
            self.assertEqual(line[self.payload_column]["request_id"], "abc")
            self.assertEqual(timeout, 30)

        post.side_effect = mock_post
        u = Uploader(
            self.host,
            self.database,
            self.table,
            self.username,
            self.password,
            None,
            self.payload_column,
            self.timeout,
        )
        u(self.frame)

        self.assertTrue(post.called)
