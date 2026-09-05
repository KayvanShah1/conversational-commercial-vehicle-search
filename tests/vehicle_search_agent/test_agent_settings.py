import pytest
from pydantic import ValidationError
from vehicle_search_agent.settings import GroqConfig


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
