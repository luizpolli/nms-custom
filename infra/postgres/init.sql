-- NMS_Custom PostgreSQL/TimescaleDB bootstrap.
-- Keep this file idempotent: Docker runs it only when the data volume is first initialized.
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
