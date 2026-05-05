# coding: utf-8
from __future__ import print_function, unicode_literals

import json
from datetime import datetime, timezone
from typing import Any, TypeAlias

import requests

UploadResponse: TypeAlias = requests.Response


class UploadFailedResponse(UploadResponse):
    def __init__(self, exception: Exception) -> None:
        self.status_code = 500
        self.exception = exception


class Uploader:
    def __init__(
        self,
        host: str,
        database: str,
        table: str,
        username: str | None,
        password: str | None,
        clickhouse_settings: dict[str, Any] | None,
        payload_column: str,
        timeout: float,
    ):
        self.host = host.rstrip("/")
        self.database = database
        self.table = table
        self.auth = (username, password) if username is not None else None
        self.clickhouse_settings = clickhouse_settings or {}
        self.payload_column = payload_column
        self.timeout = timeout
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/x-ndjson",
        }

    def __call__(self, frames: list[dict]) -> UploadResponse:
        try:
            return self.session.post(
                self.host,
                data=self._serialize_rows(frames),
                headers=self.headers,
                params=self._query_params(),
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            return UploadFailedResponse(e)

    def _serialize_rows(self, frame: list[dict]) -> str:
        rows = [
            json.dumps(self._frame_to_row(entry), separators=(",", ":"))
            for entry in frame
        ]
        return "\n".join(rows)

    def _frame_to_row(self, frame: dict[str, Any]) -> dict:
        payload = {}
        for key, value in frame.items():
            if key not in ("dt", "level", "severity", "message"):
                payload[key] = value

        return {
            "dt": _normalize_dt(frame["dt"]),
            "level": frame["level"],
            "severity": frame["severity"],
            "message": frame["message"],
            self.payload_column: payload,
        }

    def _query_params(self) -> dict[str, str]:
        params = {"query": _insert_query(self.database, self.table)}
        params.update(self.clickhouse_settings)
        return params


def _insert_query(database: str, table: str) -> str:
    return "INSERT INTO {}.{} FORMAT JSONEachRow".format(
        _quote_identifier(database),
        _quote_identifier(table),
    )


def _quote_identifier(value: str) -> str:
    return '"{}"'.format(value.replace('"', '""'))


def _normalize_dt(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
