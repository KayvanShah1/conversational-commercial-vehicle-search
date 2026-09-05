import io
import re
import wave
from collections.abc import Callable
from functools import lru_cache
from threading import Lock

from openai import OpenAI, RateLimitError
from pydantic import BaseModel
from vehicle_search_utils import OperationLogContext, get_logger

from vehicle_search_agent.settings import settings

tts_logger = get_logger("TextToSpeech")
stt_logger = get_logger("SpeechToText")
provider_logger = get_logger("SpeechProvider")
_speech_key_indices: dict[str, int] = {}
_speech_key_lock = Lock()


class SpeechResult(BaseModel):
    audio: bytes
    duration_ms: float
    format: str
    character_count: int


class TranscriptionResult(BaseModel):
    text: str
    duration_ms: float
    audio_seconds: float | None = None


@lru_cache(maxsize=1)
def _speech_clients() -> tuple[OpenAI, ...]:
    return tuple(
        OpenAI(api_key=key.get_secret_value(), base_url=settings.groq.base_url)
        for key in settings.groq.api_keys
    )


def _request_with_key_rotation[ResponseT](model: str, request: Callable[[OpenAI], ResponseT]) -> ResponseT:
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


def _text_chunks(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""

    for part in re.split(r"(?<=[.!?;,])\s+", text.strip()):
        if len(part) > max_chars:
            words = part.split()
            for word in words:
                candidate = f"{current} {word}".strip()
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    if len(word) > max_chars:
                        raise ValueError("A single word exceeds the TTS request limit.")
                    current = word
            continue

        candidate = f"{current} {part}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = part

    if current:
        chunks.append(current)
    return chunks


def _speech_text(text: str) -> str:
    """Expand compact catalog prices into words that TTS reads naturally."""

    def expand_lakh(match: re.Match[str]) -> str:
        amount = float(match.group(1))
        lakhs = int(amount)
        thousands = round((amount - lakhs) * 100)
        parts = []
        if lakhs:
            parts.append(f"{lakhs} lakh")
        if thousands:
            parts.append(f"{thousands} thousand")
        return " ".join(parts) + " rupees"

    return re.sub(r"\bINR\s+(\d+(?:\.\d+)?)L\b", expand_lakh, text, flags=re.IGNORECASE)


def _stitch_wav(audio_chunks: list[bytes]) -> bytes:
    if len(audio_chunks) == 1:
        return audio_chunks[0]

    output = io.BytesIO()
    expected_format: tuple[int, int, int, str] | None = None
    frames: list[bytes] = []

    for audio in audio_chunks:
        with wave.open(io.BytesIO(audio), "rb") as reader:
            audio_format = (
                reader.getnchannels(),
                reader.getsampwidth(),
                reader.getframerate(),
                reader.getcomptype(),
            )
            if expected_format is None:
                expected_format = audio_format
            elif audio_format != expected_format:
                raise ValueError("TTS chunks returned incompatible WAV formats.")
            frames.append(reader.readframes(reader.getnframes()))

    assert expected_format is not None
    channels, sample_width, frame_rate, compression = expected_format
    with wave.open(output, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(frame_rate)
        writer.setcomptype(compression, "not compressed")
        writer.writeframes(b"".join(frames))
    return output.getvalue()


def _wav_duration_seconds(audio: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(audio), "rb") as reader:
            return reader.getnframes() / reader.getframerate()
    except (EOFError, wave.Error):
        return None


def synthesize_speech(text: str) -> SpeechResult:
    if not text.strip():
        raise ValueError("Text-to-speech input cannot be empty.")

    operation = OperationLogContext(operation="text_to_speech")
    speech_text = _speech_text(text)
    chunks = _text_chunks(speech_text, settings.groq.tts_max_chars)
    log_context = {
        "model": settings.groq.tts_model,
        "voice": settings.groq.tts_voice,
        "character_count": len(speech_text),
        "chunk_count": len(chunks),
    }
    tts_logger.info(
        "tts_started",
        extra=operation.started_extra(status="started", **log_context),
    )

    audio_chunks = []
    for chunk in chunks:
        response = _request_with_key_rotation(
            settings.groq.tts_model,
            lambda client, text=chunk: client.audio.speech.create(
                model=settings.groq.tts_model,
                voice=settings.groq.tts_voice,
                input=text,
                response_format=settings.groq.tts_format,
            )
        )
        audio_chunks.append(response.content)
    audio = _stitch_wav(audio_chunks)

    completed_context = operation.completed_extra(status="succeeded", **log_context)

    tts_logger.info(
        "tts_completed",
        extra=completed_context,
    )

    return SpeechResult(
        audio=audio,
        duration_ms=completed_context["duration_ms"],
        format=settings.groq.tts_format,
        character_count=len(speech_text),
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

    response = _request_with_key_rotation(
        settings.groq.stt_model,
        lambda client: client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=settings.groq.stt_model,
            temperature=0,
            response_format="json",
        )
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
        audio_seconds=_wav_duration_seconds(audio_bytes),
    )
