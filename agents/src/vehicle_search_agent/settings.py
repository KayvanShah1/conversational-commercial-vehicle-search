from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from vehicle_search_utils.settings import PROJECT_ROOT, CommonSettings


class LLMConfig(BaseModel):
    provider: Literal["groq", "openrouter"] = "groq"
    model: str = "openai/gpt-oss-120b"
    api_key: SecretStr = SecretStr("<API_TOKEN>")
    base_url: str = "https://api.groq.com/openai/v1"
    tracing_enabled: bool = False


class SpeechConfig(BaseModel):
    api_key: SecretStr = SecretStr("<API_TOKEN>")
    base_url: str = "https://api.groq.com/openai/v1"

    # Speech-to-Text (STT) Configuration
    stt_model: str = "whisper-large-v3-turbo"

    # Text-to-Speech (TTS) Configuration
    tts_model: str = "canopylabs/orpheus-v1-english"
    tts_voice: str = "daniel"
    tts_format: str = "wav"


class AgentSettings(CommonSettings):
    project_name: str = Field(default="vehicle-search-agent")

    session_db_path: Path = Field(default=PROJECT_ROOT / "data" / "agent_sessions.sqlite")

    max_search_candidates: int = 50
    top_k: int = 3

    llm: LLMConfig = Field(default_factory=LLMConfig)
    speech: SpeechConfig = Field(default_factory=SpeechConfig)

    def model_post_init(self, __context, /):
        super().model_post_init(__context)
        self.session_db_path.parent.mkdir(parents=True, exist_ok=True)


settings = AgentSettings()

if __name__ == "__main__":
    from rich.pretty import pretty_repr
    from vehicle_search_utils.logger import get_logger

    logger = get_logger("AgentSettings")
    logger.info(pretty_repr(settings.model_dump()))
