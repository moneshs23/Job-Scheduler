import pytest
from sqlalchemy import text

from tests.conftest import test_engine

# Regression test for a real bug: server_default="now()" (a bare Python string) compiles to
# a quoted SQL string literal, which Postgres freezes into a fixed timestamp at the moment the
# DDL runs — every row ever inserted afterward gets that same frozen value. The fix is
# server_default=func.now() (or sa.text("now()")), which stays a live function call. This test
# asserts every timestamp-default column in the schema is still wired the correct way.
TIMESTAMP_DEFAULT_COLUMNS = [
    ("jobs", "created_at"),
    ("queues", "created_at"),
    ("api_keys", "created_at"),
    ("audit_logs", "created_at"),
    ("organization_members", "joined_at"),
    ("workers", "registered_at"),
    ("worker_heartbeats", "heartbeat_at"),
    ("job_logs", "logged_at"),
    ("dead_letter_queue", "moved_at"),
    ("organizations", "created_at"),
    ("projects", "created_at"),
    ("users", "created_at"),
]


@pytest.mark.asyncio
async def test_timestamp_columns_default_to_live_now_not_frozen_literal():
    async with test_engine.connect() as conn:
        for table, column in TIMESTAMP_DEFAULT_COLUMNS:
            result = await conn.execute(
                text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :column"
                ),
                {"table": table, "column": column},
            )
            default = result.scalar_one()
            assert default is not None, f"{table}.{column} has no server default"
            assert "now()" in default, f"{table}.{column} default is {default!r}, expected it to call now()"
            assert not default.startswith("'"), (
                f"{table}.{column} default is a frozen literal ({default!r}), "
                "not a live now() call — every row will get the same timestamp"
            )
