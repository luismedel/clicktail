# `clicktail`

`clicktail` is a minimal, conservative fork of [`logtail-python`](https://github.com/logtail/logtail-python).

The goal of this fork is intentionally narrow: keep the original handler lifecycle as intact as possible, while replacing the transport layer with ClickHouse HTTP ingestion.

## Installation

> Note: pypi upload TBD

```bash
pip install clicktail
```

## Usage

```python
import logging

from clicktail import ClickHouseHandler

handler = ClickHouseHandler(
    host="http://localhost:8123",
    database="clicktail",
    table="logs",
    username="clicktail",
    password="clicktail",
)

logger = logging.getLogger("example")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

logger.info("hello from clicktail", extra={"request_id": "abc-123"})
handler.flush()
```

Rows are inserted into ClickHouse with top-level columns `dt`, `level`, `severity`, and `message`. Everything else produced by the original frame builder, including `context` and extra attributes, is nested under the JSON column configured by `payload_column` (default: `payload`).

## Required schema

`clicktail` expects a ClickHouse table with this shape:

```sql
CREATE TABLE clicktail.logs
(
    dt DateTime64(3, 'UTC'),
    level LowCardinality(String),
    severity UInt8,
    message String,
    payload JSON
)
ENGINE = MergeTree
TTL dt + INTERVAL 3 MONTH
ORDER BY (dt, level);
```

You can change the database and table names in the handler configuration, but the column layout should stay the same.

## Local development

The repository includes a local ClickHouse 26.3 LTS setup:

```bash
docker compose up -d
```

This starts ClickHouse HTTP on `http://localhost:8123` and creates the `clicktail.logs` table with the expected schema and a default retention TTL of 3 months.

## License

This fork remains under the ISC license. See [LICENSE.md](LICENSE.md).
