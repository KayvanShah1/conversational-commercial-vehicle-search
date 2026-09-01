import pytest
from pydantic import SecretStr
from vehicle_search_utils import database
from vehicle_search_utils.settings import MotherDuckConfig


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_motherduck_connection_is_closed(monkeypatch):
    connection = FakeConnection()
    config = MotherDuckConfig(token=SecretStr("test-token"))
    monkeypatch.setattr(database.duckdb, "connect", lambda _: connection)

    with database.get_motherduck_connection(config) as active_connection:
        assert active_connection is connection
        assert not connection.closed

    assert connection.closed


def test_motherduck_connection_is_closed_after_error(monkeypatch):
    connection = FakeConnection()
    config = MotherDuckConfig(token=SecretStr("test-token"))
    monkeypatch.setattr(database.duckdb, "connect", lambda _: connection)

    with pytest.raises(RuntimeError, match="load failed"), database.get_motherduck_connection(config):
        raise RuntimeError("load failed")

    assert connection.closed


@pytest.mark.parametrize("token", ["", "<API_TOKEN>"])
def test_motherduck_connection_rejects_missing_token(monkeypatch, token):
    config = MotherDuckConfig(token=SecretStr(token))

    def unexpected_connection(_):
        pytest.fail("connection should not be attempted without a configured token")

    monkeypatch.setattr(database.duckdb, "connect", unexpected_connection)

    with (
        pytest.raises(ValueError, match="MotherDuck token is not configured"),
        database.get_motherduck_connection(config),
    ):
        pass
