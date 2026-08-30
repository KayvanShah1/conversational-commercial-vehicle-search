import polars as pl
import pytest
from vehicle_catalog_generator import generator
from vehicle_catalog_generator.quality import COUNT_COLUMNS, validate_catalog


@pytest.fixture
def catalog_dataframe(monkeypatch) -> pl.DataFrame:
    monkeypatch.setattr(generator.settings.data_generation, "record_count", 100)
    return generator.catalog_to_dataframe(generator.generate_catalog())


def test_validate_catalog_returns_quality_summary(catalog_dataframe):
    summary = validate_catalog(catalog_dataframe, expected_record_count=100)

    assert summary["row_count"] == 100
    assert summary["unique_listing_ids"] == 100
    assert summary["null_counts"] == {
        column: catalog_dataframe.get_column(column).null_count() for column in catalog_dataframe.columns
    }
    assert summary["price_inr"] == {
        "min": catalog_dataframe.get_column("price_inr").min(),
        "median": catalog_dataframe.get_column("price_inr").median(),
        "max": catalog_dataframe.get_column("price_inr").max(),
    }
    assert summary["km_driven"] == {
        "min": catalog_dataframe.get_column("km_driven").min(),
        "median": catalog_dataframe.get_column("km_driven").median(),
        "max": catalog_dataframe.get_column("km_driven").max(),
    }
    assert set(summary["counts_by"]) == set(COUNT_COLUMNS)
    assert all(sum(counts.values()) == 100 for counts in summary["counts_by"].values())


def test_validate_catalog_rejects_unexpected_row_count(catalog_dataframe):
    with pytest.raises(ValueError, match="Expected 99 catalog rows, found 100"):
        validate_catalog(catalog_dataframe, expected_record_count=99)


def test_validate_catalog_rejects_duplicate_listing_ids(catalog_dataframe):
    invalid = catalog_dataframe.with_columns(pl.lit("VEH-DUPLICATE").alias("listing_id"))

    with pytest.raises(ValueError, match="listing_id values must be unique"):
        validate_catalog(invalid, expected_record_count=100)


def test_validate_catalog_rejects_non_positive_prices(catalog_dataframe):
    invalid = catalog_dataframe.with_columns(pl.lit(0).alias("price_inr"))

    with pytest.raises(ValueError, match="price_inr values must be greater than zero"):
        validate_catalog(invalid, expected_record_count=100)


def test_validate_catalog_rejects_payload_at_or_above_gvw(catalog_dataframe):
    invalid = catalog_dataframe.with_columns(pl.col("gvw_kg").alias("payload_kg"))

    with pytest.raises(ValueError, match="gvw_kg must be greater than payload_kg"):
        validate_catalog(invalid, expected_record_count=100)


def test_validate_catalog_rejects_nulls_in_required_columns(catalog_dataframe):
    invalid = catalog_dataframe.with_columns(pl.lit(None).cast(pl.String).alias("make"))

    with pytest.raises(ValueError, match="Required columns contain nulls: make"):
        validate_catalog(invalid, expected_record_count=100)
