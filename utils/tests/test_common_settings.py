from pathlib import Path

from vehicle_search_utils.settings import CommonSettings


def test_common_settings_load_nested_environment_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("MOTHERDUCK__DATABASE", "test_catalog")
    monkeypatch.setenv("MOTHERDUCK__TOKEN", "test-token")

    settings = CommonSettings(_env_file=None, data_dir=tmp_path / "data")

    assert settings.motherduck.database == "test_catalog"
    assert settings.motherduck.token.get_secret_value() == "test-token"
    assert settings.data_dir.is_dir()


def test_project_relative_path_uses_relative_path_inside_project(tmp_path):
    settings = CommonSettings(
        _env_file=None,
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
    )

    assert settings.project_relative_path(tmp_path / "data" / "vehicles.parquet") == str(
        Path("data") / "vehicles.parquet"
    )


def test_project_relative_path_preserves_external_path(tmp_path):
    project_root = tmp_path / "project"
    external_path = tmp_path / "external" / "vehicles.parquet"
    settings = CommonSettings(
        _env_file=None,
        project_root=project_root,
        data_dir=project_root / "data",
        log_dir=project_root / "logs",
    )

    assert settings.project_relative_path(external_path) == str(external_path)
