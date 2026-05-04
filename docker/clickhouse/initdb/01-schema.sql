CREATE TABLE IF NOT EXISTS clicktail.logs
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
