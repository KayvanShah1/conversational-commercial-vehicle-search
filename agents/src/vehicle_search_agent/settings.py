from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from vehicle_search_utils.settings import PROJECT_ROOT, CommonSettings


class GroqConfig(BaseModel):
    api_key: SecretStr = SecretStr("<API_KEY>")
    base_url: str = "https://api.groq.com/openai/v1"

    # Language Model Configuration
    primary_model: str = "openai/gpt-oss-120b"
    fallback_model: str = "openai/gpt-oss-20b"

    # Speech-to-Text (STT) Configuration
    stt_model: str = "whisper-large-v3-turbo"

    # Text-to-Speech (TTS) Configuration
    tts_model: str = "canopylabs/orpheus-v1-english"
    tts_voice: str = "daniel"
    tts_format: str = "wav"
    tts_max_chars: int = 200  # Current Orpheus English request limit.


class OpenRouterConfig(BaseModel):
    api_key: SecretStr = SecretStr("<API_KEY>")
    base_url: str = "https://openrouter.ai/api/v1"


class AgentRuntimeConfig(BaseModel):
    top_k: int = Field(default=3, ge=1, le=3)
    max_turns: int = Field(default=10, ge=2, le=10)
    max_search_candidates: int = 50
    model_timeout_seconds: float = Field(default=8.0, gt=0)
    model_max_retries: int = Field(default=1, ge=0, le=3)
    tool_timeout_seconds: float = Field(default=5.0, gt=0)

    # Agent Tracing Configuration
    tracing_enabled: bool = False
    trace_include_sensitive_data: bool = False


class AgentSettings(CommonSettings):
    project_name: str = Field(default="vehicle-search-agent")

    # Agent Session and Conversation State Storage
    session_data_path: Path = PROJECT_ROOT / "data" / "sessions"
    session_db_path: Path = session_data_path / "agent_sessions.sqlite"
    conversation_state_path: Path = session_data_path / "conversation_state.sqlite"

    # Agent Configuration
    groq: GroqConfig = Field(default_factory=GroqConfig)
    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)
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
