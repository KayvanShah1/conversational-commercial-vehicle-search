import logging

from vehicle_search_utils.logger import ContextAwareFormatter


def make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="VehicleCatalogLoader",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="catalog_loaded",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formatter_separates_operation_and_timing_context():
    formatter = ContextAwareFormatter("%(name)s - %(message)s")
    record = make_record(
        operation="catalog_data_load",
        status="succeeded",
        tool="search_vehicles",
        started_at_utc="2026-08-30T16:57:49.000+00:00",
        ended_at_utc="2026-08-30T16:57:55.177+00:00",
        duration_ms=6177.0,
    )

    assert formatter.format(record) == (
        "VehicleCatalogLoader - catalog_loaded | "
        "operation=catalog_data_load status=succeeded tool=search_vehicles | "
        "started_at_utc=2026-08-30T16:57:49.000+00:00 "
        "ended_at_utc=2026-08-30T16:57:55.177+00:00 "
        "duration_ms=6177.0"
    )


def test_formatter_omits_empty_timing_group():
    formatter = ContextAwareFormatter("%(name)s - %(message)s")
    record = make_record(parquet_path="data/generated/vehicles.parquet", replace=True)

    assert formatter.format(record) == (
        "VehicleCatalogLoader - catalog_loaded | parquet_path=data/generated/vehicles.parquet replace=True"
    )
