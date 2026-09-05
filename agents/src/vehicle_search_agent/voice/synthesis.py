import io
import re
import wave

from vehicle_search_utils import OperationLogContext, get_logger

from vehicle_search_agent.settings import settings
from vehicle_search_agent.voice.models import SpeechResult
from vehicle_search_agent.voice.provider import request_with_key_rotation

tts_logger = get_logger("TextToSpeech")


def text_chunks(text: str, max_chars: int) -> list[str]:
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


def speech_text(text: str) -> str:
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


def stitch_wav(audio_chunks: list[bytes]) -> bytes:
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


def synthesize_speech(text: str) -> SpeechResult:
    if not text.strip():
        raise ValueError("Text-to-speech input cannot be empty.")

    operation = OperationLogContext(operation="text_to_speech")
    normalized_text = speech_text(text)
    chunks = text_chunks(normalized_text, settings.groq.tts_max_chars)
    log_context = {
        "model": settings.groq.tts_model,
        "voice": settings.groq.tts_voice,
        "character_count": len(normalized_text),
        "chunk_count": len(chunks),
    }
    tts_logger.info(
        "tts_started",
        extra=operation.started_extra(status="started", **log_context),
    )

    audio_chunks = []
    for chunk in chunks:
        response = request_with_key_rotation(
            settings.groq.tts_model,
            lambda client, text=chunk: client.audio.speech.create(
                model=settings.groq.tts_model,
                voice=settings.groq.tts_voice,
                input=text,
                response_format=settings.groq.tts_format,
            ),
        )
        audio_chunks.append(response.content)
    audio = stitch_wav(audio_chunks)

    completed_context = operation.completed_extra(status="succeeded", **log_context)

    tts_logger.info(
        "tts_completed",
        extra=completed_context,
    )

    return SpeechResult(
        audio=audio,
        duration_ms=completed_context["duration_ms"],
        format=settings.groq.tts_format,
        character_count=len(normalized_text),
    )
