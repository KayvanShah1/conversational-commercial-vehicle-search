import random
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from vehicle_search_utils.logger import get_logger
from vehicle_search_utils.operation import OperationLogContext

from vehicle_catalog_generator.models import VehicleCondition, VehicleListing, VehicleReference
from vehicle_catalog_generator.quality import validate_catalog
from vehicle_catalog_generator.reference_data import (
    CITY_WEIGHTS,
    CONDITION_PRICE_FACTORS,
    CONDITION_WEIGHTS,
    GENERATION_PARAMETERS,
    VEHICLE_REFERENCES,
    WEIGHT_CLASS_WEIGHTS,
)
from vehicle_catalog_generator.settings import settings

logger = get_logger("VehicleCatalogGenerator")


def weighted_choice[Choice](weights: dict[Choice, float]) -> Choice:
    return random.choices(population=list(weights), weights=list(weights.values()), k=1)[0]


def generate_km_driven(age: int) -> int:
    if age <= 0:
        return random.randint(*GENERATION_PARAMETERS.new_vehicle_km_range)

    cfg = settings.data_generation
    km_per_year = random.randint(cfg.min_km_per_year, cfg.max_km_per_year)
    km_driven = int(age * km_per_year * random.uniform(*GENERATION_PARAMETERS.km_variance_range))
    return max(GENERATION_PARAMETERS.minimum_km_driven, km_driven)


def generate_condition() -> VehicleCondition:
    return weighted_choice(CONDITION_WEIGHTS)


def choose_vehicle_reference() -> VehicleReference:
    weight_class = weighted_choice(WEIGHT_CLASS_WEIGHTS)
    compatible_references = [reference for reference in VEHICLE_REFERENCES if reference.weight_class == weight_class]
    return random.choice(compatible_references)


def calculate_price(
    new_vehicle_price_anchor_inr: int,
    age: int,
    km_driven: int,
    condition: VehicleCondition,
) -> int:
    age_factor = max(
        GENERATION_PARAMETERS.minimum_age_factor,
        (1 - GENERATION_PARAMETERS.annual_depreciation_rate) ** age,
    )
    mileage_factor = max(
        GENERATION_PARAMETERS.minimum_mileage_factor,
        1 - (km_driven / GENERATION_PARAMETERS.mileage_depreciation_distance_km),
    )
    condition_factor = CONDITION_PRICE_FACTORS[condition]
    market_noise = random.uniform(*GENERATION_PARAMETERS.market_noise_range)

    price = new_vehicle_price_anchor_inr * age_factor * mileage_factor * condition_factor * market_noise
    rounded_price = round(price / GENERATION_PARAMETERS.price_rounding_interval_inr)
    return max(
        GENERATION_PARAMETERS.minimum_price_inr,
        int(rounded_price * GENERATION_PARAMETERS.price_rounding_interval_inr),
    )


def generate_vehicle_listing(index: int) -> VehicleListing:
    cfg = settings.data_generation
    reference = choose_vehicle_reference()
    age = random.randint(cfg.min_vehicle_age, cfg.max_vehicle_age)
    km_driven = generate_km_driven(age)
    condition = generate_condition()

    return VehicleListing(
        listing_id=f"VEH-{index:06d}",
        make=reference.make,
        model=reference.model,
        year=datetime.now(UTC).year - age,
        price_inr=calculate_price(reference.new_vehicle_price_anchor_inr, age, km_driven, condition),
        km_driven=km_driven,
        fuel=reference.fuel,
        payload_kg=reference.payload_kg,
        payload_is_estimated=reference.payload_is_estimated,
        gvw_kg=reference.gvw_kg,
        vehicle_category=reference.vehicle_category,
        weight_class=reference.weight_class,
        body_type=reference.body_type,
        axle_count=reference.axle_count,
        city=weighted_choice(CITY_WEIGHTS),
        papers_verified=random.random() < cfg.papers_verified_probability,
        condition=condition,
        purpose_tags=reference.purpose_tags,
        spec_source_url=reference.spec_source_url,
    )


def generate_catalog() -> list[VehicleListing]:
    cfg = settings.data_generation
    random.seed(cfg.seed)
    return [generate_vehicle_listing(index=i + 1) for i in range(cfg.record_count)]


def catalog_to_dataframe(listings: list[VehicleListing]) -> pl.DataFrame:
    return pl.DataFrame([listing.model_dump() for listing in listings])


def write_catalog(dataframe: pl.DataFrame) -> tuple[Path, Path]:
    cfg = settings.data_generation
    parquet_path = settings.generated_data_dir / f"{cfg.output_filename}.parquet"
    csv_path = settings.generated_data_dir / f"{cfg.output_filename}.csv"
    dataframe.write_parquet(parquet_path)

    csv_dataframe = dataframe.with_columns(pl.col("purpose_tags").list.join("|"))
    csv_dataframe.write_csv(csv_path)
    return parquet_path, csv_path


def write_reference_catalog() -> Path:
    reference_path = settings.generated_data_dir / "vehicle_reference_catalog.csv"
    reference_dataframe = pl.DataFrame([reference.model_dump(mode="json") for reference in VEHICLE_REFERENCES])
    reference_dataframe = reference_dataframe.with_columns(pl.col("purpose_tags").list.join("|"))
    reference_dataframe.write_csv(reference_path)
    return reference_path


def generate_catalog_files() -> tuple[Path, Path]:
    operation = OperationLogContext(operation="catalog_data_generation")
    logger.info("catalog_generation_started", extra=operation.started_extra(status="started"))

    dataframe = catalog_to_dataframe(generate_catalog())
    validate_catalog(dataframe, expected_record_count=settings.data_generation.record_count)
    parquet_path, csv_path = write_catalog(dataframe)
    reference_path = write_reference_catalog()

    logger.info(
        "catalog_generated",
        extra=operation.completed_extra(
            status="succeeded",
            row_count=dataframe.height,
            parquet_path=settings.project_relative_path(parquet_path),
            csv_path=settings.project_relative_path(csv_path),
            reference_catalog_path=settings.project_relative_path(reference_path),
        ),
    )
    return parquet_path, csv_path


def main() -> None:
    generate_catalog_files()


if __name__ == "__main__":
    main()
