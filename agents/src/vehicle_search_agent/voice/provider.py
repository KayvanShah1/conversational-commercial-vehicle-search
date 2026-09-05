from collections.abc import Callable
from functools import lru_cache
from threading import Lock

from openai import OpenAI, RateLimitError
from vehicle_search_utils import get_logger

from vehicle_search_agent.settings import settings

provider_logger = get_logger("SpeechProvider")
_speech_key_indices: dict[str, int] = {}
_speech_key_lock = Lock()


@lru_cache(maxsize=1)
def _speech_clients() -> tuple[OpenAI, ...]:
    return tuple(
        OpenAI(api_key=key.get_secret_value(), base_url=settings.groq.base_url) for key in settings.groq.api_keys
    )


def request_with_key_rotation[ResponseT](model: str, request: Callable[[OpenAI], ResponseT]) -> ResponseT:
    clients = _speech_clients()
    with _speech_key_lock:
        start_index = _speech_key_indices.get(model, 0) % len(clients)

    for offset in range(len(clients)):
        key_index = (start_index + offset) % len(clients)
        try:
            response = request(clients[key_index])
        except RateLimitError:
            if offset == len(clients) - 1:
                raise
            next_index = (key_index + 1) % len(clients)
            with _speech_key_lock:
                _speech_key_indices[model] = next_index
            provider_logger.warning(
                "speech_key_rotated",
                extra={
                    "model": model,
                    "previous_key_number": key_index + 1,
                    "next_key_number": next_index + 1,
                },
            )
        else:
            with _speech_key_lock:
                _speech_key_indices[model] = key_index
            return response
    raise RuntimeError("No Groq speech client is configured.")
