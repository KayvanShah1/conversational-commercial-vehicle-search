from collections.abc import Generator
from contextlib import contextmanager

import duckdb

from vehicle_search_utils.settings import MotherDuckConfig


@contextmanager
def get_motherduck_connection(
    config: MotherDuckConfig,
) -> Generator[duckdb.DuckDBPyConnection]:
    """Open a MotherDuck connection and always close it after use."""
    token = config.token.get_secret_value()

    if not token or token == "<API_TOKEN>":
        raise ValueError("MotherDuck token is not configured.")

    connection_string = f"md:{config.database}?motherduck_token={token}"
    connection = duckdb.connect(connection_string)
    try:
        yield connection
    finally:
        connection.close()
