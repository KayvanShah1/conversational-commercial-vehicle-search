import pytest
from pydantic import ValidationError
from vehicle_catalog_generator.settings import DataGenerationConfig, Settings


def test_nested_environment_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("MOTHERDUCK__DATABASE", "test_catalog")
    monkeypatch.setenv("MOTHERDUCK__TOKEN", "test-token")
    monkeypatch.setenv("DATA_GENERATION__RECORD_COUNT", "125")
    monkeypatch.setenv("DATA_GENERATION__REPLACE", "true")

    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        generated_data_dir=tmp_path / "data" / "generated",
    )

    assert settings.motherduck.database == "test_catalog"
    assert settings.motherduck.token.get_secret_value() == "test-token"
    assert settings.data_generation.record_count == 125
    assert settings.data_generation.replace is True
    assert settings.generated_data_dir.is_dir()


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        (
            {"min_vehicle_age": 10, "max_vehicle_age": 5},
            "min_vehicle_age must be less than or equal to max_vehicle_age",
        ),
        (
            {"min_km_per_year": 40_000, "max_km_per_year": 20_000},
            "min_km_per_year must be less than or equal to max_km_per_year",
        ),
    ],
)
def test_data_generation_ranges_must_be_ordered(overrides, expected_message):
    with pytest.raises(ValidationError, match=expected_message):
        DataGenerationConfig(**overrides)
