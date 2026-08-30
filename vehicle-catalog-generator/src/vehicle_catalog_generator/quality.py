from typing import Any

import polars as pl

from vehicle_catalog_generator.models import VehicleListing

NULLABLE_COLUMNS = {"payload_kg"}
COUNT_COLUMNS = ("make", "fuel", "city", "weight_class", "body_type")


def _numeric_summary(dataframe: pl.DataFrame, column: str) -> dict[str, int | float]:
    series = dataframe.get_column(column)
    return {
        "min": series.min(),
        "median": series.median(),
        "max": series.max(),
    }


def _value_counts(dataframe: pl.DataFrame, column: str) -> dict[str, int]:
    rows = dataframe.group_by(column).agg(pl.len().alias("count")).sort(column).to_dicts()
    return {str(row[column]): row["count"] for row in rows}


def validate_catalog(
    dataframe: pl.DataFrame,
    *,
    expected_record_count: int,
) -> dict[str, Any]:
    """Validate generated-record invariants and return a compact quality summary."""
    expected_columns = set(VehicleListing.model_fields)
    missing_columns = expected_columns - set(dataframe.columns)
    if missing_columns:
        raise ValueError(f"Catalog is missing required columns: {', '.join(sorted(missing_columns))}")

    if dataframe.height != expected_record_count:
        raise ValueError(f"Expected {expected_record_count} catalog rows, found {dataframe.height}")

    unique_listing_ids = dataframe.get_column("listing_id").n_unique()
    if unique_listing_ids != dataframe.height:
        raise ValueError("listing_id values must be unique")

    required_columns = expected_columns - NULLABLE_COLUMNS
    null_counts = {column: dataframe.get_column(column).null_count() for column in dataframe.columns}
    columns_with_nulls = sorted(column for column in required_columns if null_counts[column] > 0)
    if columns_with_nulls:
        raise ValueError(f"Required columns contain nulls: {', '.join(columns_with_nulls)}")

    if dataframe.filter(pl.col("price_inr") <= 0).height:
        raise ValueError("price_inr values must be greater than zero")

    invalid_payloads = dataframe.filter(
        pl.col("payload_kg").is_not_null() & (pl.col("gvw_kg") <= pl.col("payload_kg"))
    ).height
    if invalid_payloads:
        raise ValueError("gvw_kg must be greater than payload_kg when payload_kg is present")

    return {
        "row_count": dataframe.height,
        "unique_listing_ids": unique_listing_ids,
        "null_counts": null_counts,
        "price_inr": _numeric_summary(dataframe, "price_inr"),
        "km_driven": _numeric_summary(dataframe, "km_driven"),
        "counts_by": {column: _value_counts(dataframe, column) for column in COUNT_COLUMNS},
    }
