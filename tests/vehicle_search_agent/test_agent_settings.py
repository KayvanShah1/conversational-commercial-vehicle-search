import pytest
from pydantic import SecretStr, ValidationError
from vehicle_search_agent.settings import GroqConfig, OpenRouterConfig


@pytest.mark.parametrize("api_keys", [[], [""], ["   "], ["<API_KEY>"]])
def test_groq_api_key_is_required(api_keys: list[str]) -> None:
    with pytest.raises(ValidationError):
        GroqConfig(api_keys=api_keys)


def test_groq_api_key_is_trimmed() -> None:
    config = GroqConfig(api_keys=["  configured  "])

    assert config.api_keys[0].get_secret_value() == "configured"


def test_groq_keys_are_trimmed_and_unique() -> None:
    config = GroqConfig(api_keys=["primary", "  secondary  ", "primary"])

    assert [key.get_secret_value() for key in config.api_keys] == ["primary", "secondary"]


@pytest.mark.parametrize("api_key", [None, "", "   ", "<API_KEY>"])
def test_openrouter_api_key_is_optional(api_key: str | None) -> None:
    config = OpenRouterConfig(api_key=api_key)

    assert config.api_key is None


def test_openrouter_api_key_is_trimmed() -> None:
    config = OpenRouterConfig(api_key=SecretStr("  configured  "))

    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "configured"
