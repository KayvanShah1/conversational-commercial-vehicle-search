import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import duckdb
import pytest
from vehicle_search_agent.settings import settings
from vehicle_search_utils.database import get_motherduck_connection

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MOTHERDUCK_INTEGRATION_TESTS") != "1",
    reason="Set RUN_MOTHERDUCK_INTEGRATION_TESTS=1 to run live MotherDuck tests.",
)

TABLE_NAME_PATTERN = r"agent_read_only_check_[0-9a-f]{32}"


def _verify_read_only_connection(table_name: str) -> None:
    if not re.fullmatch(TABLE_NAME_PATTERN, table_name):
        raise ValueError("Unexpected verification table name.")

    with get_motherduck_connection(settings.motherduck, read_only=True) as connection:
        access_mode = connection.execute("SELECT current_setting('access_mode')").fetchone()[0]
        value = connection.execute(f"SELECT value FROM {table_name}").fetchone()[0]

        try:
            connection.execute(f"INSERT INTO {table_name} VALUES (99)")
        except duckdb.Error as error:
            write_error = str(error)
        else:
            raise AssertionError("Read-only MotherDuck connection accepted an INSERT.")

    print(f"access_mode={access_mode}")
    print(f"read_value={value}")
    print(f"write_error={write_error}")


def test_agent_connection_reads_but_cannot_write() -> None:
    table_name = f"agent_read_only_check_{uuid4().hex}"

    try:
        with get_motherduck_connection(settings.motherduck) as connection:
            connection.execute(f"CREATE TABLE {table_name} (value INTEGER)")
            connection.execute(f"INSERT INTO {table_name} VALUES (42)")

        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--verify-read-only", table_name],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert "access_mode=read_only" in result.stdout
        assert "read_value=42" in result.stdout
        assert "attached in read-only mode" in result.stdout
    finally:
        with get_motherduck_connection(settings.motherduck) as connection:
            connection.execute(f"DROP TABLE IF EXISTS {table_name}")
            remaining_tables = connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
                [table_name],
            ).fetchone()[0]

        assert remaining_tables == 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--verify-read-only":
        raise SystemExit("Expected --verify-read-only <table_name>.")

    _verify_read_only_connection(sys.argv[2])
