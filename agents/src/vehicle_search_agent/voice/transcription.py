import io
import wave

from vehicle_search_utils import OperationLogContext, get_logger

from vehicle_search_agent.settings import settings
from vehicle_search_agent.voice.models import TranscriptionResult
from vehicle_search_agent.voice.provider import request_with_key_rotation

stt_logger = get_logger("SpeechToText")


def wav_duration_seconds(audio: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(audio), "rb") as reader:
            frame_size = reader.getnchannels() * reader.getsampwidth()
            frame_rate = reader.getframerate()
            frames = reader.readframes(reader.getnframes())
            return len(frames) / frame_size / frame_rate
    except (EOFError, wave.Error):
        return None


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

    response = request_with_key_rotation(
        settings.groq.stt_model,
        lambda client: client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=settings.groq.stt_model,
            temperature=0,
            response_format="json",
        ),
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
        audio_seconds=wav_duration_seconds(audio_bytes),
    )
