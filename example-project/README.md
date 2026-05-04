# Clicktail Python example project

This example shows how to send Python logs to ClickHouse over HTTP with `clicktail`.

## Installation

```bash
pip install clicktail
```

## Run

```bash
make run
```

This target loads `example-project/.env` and runs the script with those values.

Example `.env`:

```bash
CLICKTAIL_HOST=http://localhost:8123
CLICKTAIL_DATABASE=clicktail
CLICKTAIL_TABLE=logs
CLICKTAIL_USERNAME=clicktail
CLICKTAIL_PASSWORD=clicktail
```

The handler preserves the original queueing and worker-thread behavior from `logtail-python`, but writes batches to ClickHouse using `INSERT INTO ... FORMAT JSONEachRow`.
