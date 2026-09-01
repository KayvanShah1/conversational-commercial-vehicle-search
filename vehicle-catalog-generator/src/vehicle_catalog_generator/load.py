from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import duckdb
from vehicle_search_utils.logger import get_logger
from vehicle_search_utils.operation import OperationLogContext

from vehicle_catalog_generator import generator
from vehicle_catalog_generator.settings import settings

logger = get_logger("VehicleCatalogLoader")


def _catalog_path() -> Path:
    return settings.generated_data_dir / f"{settings.data_generation.output_filename}.parquet"


@contextmanager
def get_motherduck_connection() -> Generator[duckdb.DuckDBPyConnection]:
    token = settings.motherduck.token.get_secret_value()

    if not token or token == "<API_TOKEN>":
        raise ValueError("MotherDuck token is not configured.")

    connection_string = f"md:{settings.motherduck.database}?motherduck_token={token}"
    connection = duckdb.connect(connection_string)
    try:
        yield connection
    finally:
        connection.close()


def ensure_catalog_exists() -> Path:
    parquet_path = _catalog_path()
    replace = settings.data_generation.replace

    if replace or not parquet_path.exists():
        generator.generate_catalog_files()

    return parquet_path


def load_catalog() -> int:
    operation = OperationLogContext(operation="catalog_data_load")
    logger.info("catalog_load_started", extra=operation.started_extra(status="started"))

    parquet_path = ensure_catalog_exists()

    with get_motherduck_connection() as connection:
        connection.execute(
            """
            CREATE OR REPLACE TABLE vehicles AS
            SELECT *
            FROM read_parquet(?)
            """,
            [str(parquet_path)],
        )
        count = connection.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]

    logger.info(
        "catalog_loaded",
        extra=operation.completed_extra(
            status="succeeded",
            row_count=count,
            database=settings.motherduck.database,
            table="vehicles",
        ),
    )
    return count


if __name__ == "__main__":
    load_catalog()
