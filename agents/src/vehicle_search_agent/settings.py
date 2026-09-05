from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, field_validator
from vehicle_search_utils.settings import PROJECT_ROOT, CommonSettings


class GroqConfig(BaseModel):
    api_keys: list[SecretStr] = Field(min_length=1)
    base_url: str = "https://api.groq.com/openai/v1"

    # Language Model Configuration
    primary_model: str = "openai/gpt-oss-120b"
    fallback_models: list[str] = Field(
        default_factory=lambda: ["openai/gpt-oss-20b", "qwen/qwen3.6-27b", "qwen/qwen3.8-27b"],
        min_length=1,
    )

    # Speech-to-Text (STT) Configuration
    stt_model: str = "whisper-large-v3-turbo"

    # Text-to-Speech (TTS) Configuration
    tts_model: str = "canopylabs/orpheus-v1-english"
    tts_voice: str = "troy"
    tts_format: str = "wav"
    tts_max_chars: int = 200  # Per-request limit; longer replies are split before synthesis.

    @field_validator("api_keys")
    @classmethod
    def validate_api_keys(cls, api_keys: list[SecretStr]) -> list[SecretStr]:
        unique: dict[str, SecretStr] = {}
        for key in api_keys:
            value = key.get_secret_value().strip()
            if not value or value == "<API_KEY>":
                raise ValueError("GROQ__API_KEYS contains an unconfigured key.")
            unique.setdefault(value, SecretStr(value))
        return list(unique.values())


class AgentRuntimeConfig(BaseModel):
    max_turns: int = Field(default=6, ge=2, le=10)
    model_timeout_seconds: float = Field(default=8.0, gt=0)
    tool_timeout_seconds: float = Field(default=15.0, gt=0)

    # Agent Tracing Configuration
    tracing_enabled: bool = False
    trace_include_sensitive_data: bool = False


class AgentSettings(CommonSettings):
    project_name: str = Field(default="vehicle-search-agent")

    # Agent Session and Conversation State Storage
    session_data_path: Path = PROJECT_ROOT / "data" / "sessions"
    session_db_path: Path = session_data_path / "agent_sessions.sqlite"

    # Agent Configuration
    groq: GroqConfig = Field(default_factory=GroqConfig)
    agent_runtime: AgentRuntimeConfig = Field(default_factory=AgentRuntimeConfig)

    def model_post_init(self, __context, /):
        super().model_post_init(__context)
        self.session_data_path.mkdir(parents=True, exist_ok=True)


settings = AgentSettings()

if __name__ == "__main__":
    from rich.pretty import pretty_repr
    from vehicle_search_utils.logger import get_logger

    logger = get_logger("AgentSettings")
    logger.info(pretty_repr(settings.model_dump()))
