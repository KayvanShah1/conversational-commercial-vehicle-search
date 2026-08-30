from vehicle_catalog_generator.settings import Settings


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
