from collections import Counter

import polars as pl
from vehicle_catalog_generator import generator
from vehicle_catalog_generator.models import VehicleBodyType, VehicleCategory, VehicleCondition, VehicleWeightClass
from vehicle_catalog_generator.reference_data import (
    CONDITION_PRICE_FACTORS,
    CONDITION_WEIGHTS,
    VEHICLE_REFERENCES,
    WEIGHT_CLASS_WEIGHTS,
)


def test_vehicle_condition_reference_data_is_complete():
    assert set(CONDITION_WEIGHTS) == set(VehicleCondition)
    assert set(CONDITION_PRICE_FACTORS) == set(VehicleCondition)
    assert sum(CONDITION_WEIGHTS.values()) == 1.0


def test_vehicle_weight_class_distribution_is_complete():
    assert set(WEIGHT_CLASS_WEIGHTS) == set(VehicleWeightClass)
    assert sum(WEIGHT_CLASS_WEIGHTS.values()) == 1.0


def test_vehicle_references_cover_search_taxonomy():
    assert all(reference.spec_source_url for reference in VEHICLE_REFERENCES)
    assert {reference.weight_class for reference in VEHICLE_REFERENCES} == set(VehicleWeightClass)
    assert {reference.body_type for reference in VEHICLE_REFERENCES} == set(VehicleBodyType)
    assert {reference.axle_count for reference in VEHICLE_REFERENCES} == {2, 3, 4, 5}
    assert {"BharatBenz", "Eicher"} <= {reference.make for reference in VEHICLE_REFERENCES}
    assert {
        (reference.make, reference.model)
        for reference in VEHICLE_REFERENCES
        if reference.payload_is_estimated
    } == {
        ("Tata", "Ultra T.16"),
        ("Tata", "Signa 4932.T"),
        ("Mahindra", "Blazo X 48"),
    }


def test_catalog_is_reproducible(monkeypatch):
    monkeypatch.setattr(generator.settings.data_generation, "record_count", 100)

    first = generator.generate_catalog()
    second = generator.generate_catalog()

    assert first == second
    assert first[0].listing_id == "VEH-000001"
    assert isinstance(first[0].condition, VehicleCondition)
    assert isinstance(first[0].vehicle_category, VehicleCategory)
    assert isinstance(first[0].weight_class, VehicleWeightClass)
    assert isinstance(first[0].body_type, VehicleBodyType)
    assert first[0].axle_count >= 2
    assert "price_inr" in first[0].model_dump()
    assert "new_vehicle_price_anchor_inr" not in first[0].model_dump()
    assert "spec_source_url" not in first[0].model_dump()
    assert "payload_is_estimated" not in first[0].model_dump()
    assert len(first) == 100


def test_catalog_follows_weight_class_distribution(monkeypatch):
    monkeypatch.setattr(generator.settings.data_generation, "record_count", 1000)

    counts = Counter(listing.weight_class for listing in generator.generate_catalog())

    for weight_class, expected_share in WEIGHT_CLASS_WEIGHTS.items():
        observed_share = counts[weight_class] / 1000
        assert abs(observed_share - expected_share) <= 0.05


def test_write_catalog_creates_parquet_and_csv(monkeypatch, tmp_path):
    monkeypatch.setattr(generator.settings, "generated_data_dir", tmp_path)
    monkeypatch.setattr(generator.settings.data_generation, "output_filename", "test-vehicles")
    dataframe = pl.DataFrame(
        {
            "listing_id": ["VEH-000001"],
            "purpose_tags": [["city_delivery", "last_mile"]],
        }
    )

    parquet_path, csv_path = generator.write_catalog(dataframe)

    assert parquet_path.exists()
    assert csv_path.exists()
    assert pl.read_parquet(parquet_path).to_dicts() == [
        {
            "listing_id": "VEH-000001",
            "purpose_tags": ["city_delivery", "last_mile"],
        }
    ]
    assert pl.read_csv(csv_path).to_dicts() == [
        {
            "listing_id": "VEH-000001",
            "purpose_tags": "city_delivery|last_mile",
        }
    ]


def test_write_reference_catalog_exports_provenance(monkeypatch, tmp_path):
    monkeypatch.setattr(generator.settings, "generated_data_dir", tmp_path)

    reference_path = generator.write_reference_catalog()
    reference_dataframe = pl.read_csv(reference_path)

    assert reference_path == tmp_path / "vehicle_reference_catalog.csv"
    assert reference_dataframe.height == len(VEHICLE_REFERENCES)
    assert {"spec_source_url", "payload_is_estimated"} <= set(reference_dataframe.columns)
    assert reference_dataframe.get_column("spec_source_url").null_count() == 0
    assert reference_dataframe.filter(pl.col("payload_is_estimated")).height == 3
