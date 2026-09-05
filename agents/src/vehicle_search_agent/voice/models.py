from pydantic import BaseModel


class SpeechResult(BaseModel):
    audio: bytes
    duration_ms: float
    format: str
    character_count: int


class TranscriptionResult(BaseModel):
    text: str
    duration_ms: float
    audio_seconds: float | None = None
