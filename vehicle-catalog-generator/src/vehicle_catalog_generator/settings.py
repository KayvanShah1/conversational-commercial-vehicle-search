from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, model_validator
from vehicle_search_utils.settings import PROJECT_ROOT, CommonSettings


class DataGenerationConfig(BaseModel):
    record_count: int = Field(default=1000, ge=100, le=10_000)
    seed: int = Field(default=42)
    replace: bool = Field(default=False)

    min_vehicle_age: int = Field(default=1, ge=0)
    max_vehicle_age: int = Field(default=12, ge=1)

    min_km_per_year: int = Field(default=8_000, ge=0)
    max_km_per_year: int = Field(default=35_000, ge=1)

    papers_verified_probability: float = Field(default=0.82, ge=0.0, le=1.0)

    output_filename: str = Field(default="vehicles")

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        """Reject configuration ranges whose lower bound exceeds the upper bound."""
        if self.min_vehicle_age > self.max_vehicle_age:
            raise ValueError("min_vehicle_age must be less than or equal to max_vehicle_age")
        if self.min_km_per_year > self.max_km_per_year:
            raise ValueError("min_km_per_year must be less than or equal to max_km_per_year")
        return self


class Settings(CommonSettings):
    generated_data_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "generated",
        description="Directory for generated datasets",
    )

    data_generation: DataGenerationConfig = Field(default_factory=DataGenerationConfig)

    def model_post_init(self, __context, /):
        """Ensure directories exist on startup."""
        super().model_post_init(__context)
        self.generated_data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()

if __name__ == "__main__":
    from rich.pretty import pretty_repr
    from vehicle_search_utils.logger import get_logger

    logger = get_logger("VehicleCatalogGeneratorSettings")
    logger.info(pretty_repr(settings.model_dump()))
