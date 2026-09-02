import pytest
from pydantic import SecretStr, ValidationError
from vehicle_search_agent.settings import GroqConfig, OpenRouterConfig


@pytest.mark.parametrize("api_key", ["", "   ", "<API_KEY>"])
def test_groq_api_key_is_required(api_key: str) -> None:
    with pytest.raises(ValidationError, match="GROQ__API_KEY is not configured"):
        GroqConfig(api_key=api_key)


def test_groq_api_key_is_trimmed() -> None:
    config = GroqConfig(api_key="  configured  ")

    assert config.api_key.get_secret_value() == "configured"


@pytest.mark.parametrize("api_key", [None, "", "   ", "<API_KEY>"])
def test_openrouter_api_key_is_optional(api_key: str | None) -> None:
    config = OpenRouterConfig(api_key=api_key)

    assert config.api_key is None


def test_openrouter_api_key_is_trimmed() -> None:
    config = OpenRouterConfig(api_key=SecretStr("  configured  "))

    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "configured"
