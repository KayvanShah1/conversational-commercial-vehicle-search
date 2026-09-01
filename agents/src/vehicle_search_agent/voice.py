from openai import OpenAI
from pydantic import BaseModel
from vehicle_search_utils import OperationLogContext, get_logger

from vehicle_search_agent.settings import settings

tts_logger = get_logger("TextToSpeech")
stt_logger = get_logger("SpeechToText")


class SpeechResult(BaseModel):
    audio: bytes
    duration_ms: float
    format: str


class TranscriptionResult(BaseModel):
    text: str
    duration_ms: float


def _speech_client() -> OpenAI:
    api_key = settings.groq.api_key.get_secret_value()

    if not api_key or api_key == "<API_TOKEN>":
        raise ValueError("Speech API key is not configured.")

    return OpenAI(
        api_key=api_key,
        base_url=settings.groq.base_url,
    )


def synthesize_speech(text: str) -> SpeechResult:
    operation = OperationLogContext(operation="text_to_speech")
    log_context = {
        "model": settings.groq.tts_model,
        "voice": settings.groq.tts_voice,
        "character_count": len(text),
    }
    tts_logger.info(
        "tts_started",
        extra=operation.started_extra(status="started", **log_context),
    )

    response = _speech_client().audio.speech.create(
        model=settings.groq.tts_model,
        voice=settings.groq.tts_voice,
        input=text,
        response_format=settings.groq.tts_format,
    )
    audio = response.content

    completed_context = operation.completed_extra(status="succeeded", **log_context)

    tts_logger.info(
        "tts_completed",
        extra=completed_context,
    )

    return SpeechResult(
        audio=audio,
        duration_ms=completed_context["duration_ms"],
        format=settings.groq.tts_format,
    )


def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "recording.wav",
) -> TranscriptionResult:
    operation = OperationLogContext(operation="speech_to_text")
    log_context = {
        "model": settings.groq.stt_model,
        "audio_filename": filename,
        "audio_byte_count": len(audio_bytes),
    }
    stt_logger.info(
        "stt_started",
        extra=operation.started_extra(status="started", **log_context),
    )

    response = _speech_client().audio.transcriptions.create(
        file=(filename, audio_bytes),
        model=settings.groq.stt_model,
        temperature=0,
        response_format="json",
    )
    text = response.text.strip()

    completed_context = operation.completed_extra(
        status="succeeded",
        character_count=len(text),
        **log_context,
    )

    stt_logger.info(
        "stt_completed",
        extra=completed_context,
    )

    return TranscriptionResult(
        text=text,
        duration_ms=completed_context["duration_ms"],
    )
