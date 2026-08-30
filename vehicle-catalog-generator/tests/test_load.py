import pytest
from pydantic import SecretStr
from vehicle_catalog_generator import load


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_motherduck_connection_is_closed(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(load.settings.motherduck, "token", SecretStr("test-token"))
    monkeypatch.setattr(load.duckdb, "connect", lambda _: connection)

    with load.get_motherduck_connection() as active_connection:
        assert active_connection is connection
        assert not connection.closed

    assert connection.closed


def test_motherduck_connection_is_closed_after_error(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(load.settings.motherduck, "token", SecretStr("test-token"))
    monkeypatch.setattr(load.duckdb, "connect", lambda _: connection)

    with pytest.raises(RuntimeError, match="load failed"), load.get_motherduck_connection():
        raise RuntimeError("load failed")

    assert connection.closed


def test_missing_catalog_runs_generator(monkeypatch, tmp_path):
    monkeypatch.setattr(load.settings, "generated_data_dir", tmp_path)
    monkeypatch.setattr(load.settings.data_generation, "output_filename", "missing")
    monkeypatch.setattr(load.settings.data_generation, "replace", False)
    parquet_path = tmp_path / "missing.parquet"
    generation_calls = []

    def generate_catalog_files():
        generation_calls.append(True)
        parquet_path.touch()
        return parquet_path, tmp_path / "missing.csv"

    monkeypatch.setattr(load.generator, "generate_catalog_files", generate_catalog_files)

    assert load.ensure_catalog_exists() == parquet_path
    assert generation_calls == [True]


def test_existing_catalog_does_not_run_generator(monkeypatch, tmp_path):
    monkeypatch.setattr(load.settings, "generated_data_dir", tmp_path)
    monkeypatch.setattr(load.settings.data_generation, "output_filename", "vehicles")
    monkeypatch.setattr(load.settings.data_generation, "replace", False)
    parquet_path = tmp_path / "vehicles.parquet"
    parquet_path.touch()

    def unexpected_generation():
        pytest.fail("generator should not run when the catalog already exists")

    monkeypatch.setattr(load.generator, "generate_catalog_files", unexpected_generation)

    assert load.ensure_catalog_exists() == parquet_path


def test_replace_regenerates_existing_catalog(monkeypatch, tmp_path):
    monkeypatch.setattr(load.settings, "generated_data_dir", tmp_path)
    monkeypatch.setattr(load.settings.data_generation, "output_filename", "vehicles")
    monkeypatch.setattr(load.settings.data_generation, "replace", True)
    parquet_path = tmp_path / "vehicles.parquet"
    parquet_path.touch()
    generation_calls = []

    def generate_catalog_files():
        generation_calls.append(True)
        return parquet_path, tmp_path / "vehicles.csv"

    monkeypatch.setattr(load.generator, "generate_catalog_files", generate_catalog_files)

    assert load.ensure_catalog_exists() == parquet_path
    assert generation_calls == [True]
