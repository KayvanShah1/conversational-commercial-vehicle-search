import io
import wave
from types import SimpleNamespace

import vehicle_search_agent.voice.provider as voice_provider
from vehicle_search_agent.voice import speech_text, synthesize_speech, text_chunks, wav_duration_seconds


def _wav(frames: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(1)
        writer.setframerate(8_000)
        writer.writeframes(frames)
    return output.getvalue()


def test_text_chunks_stay_within_the_provider_limit():
    text = "First sentence is short. " + "word " * 60

    chunks = text_chunks(text, 80)

    assert " ".join(chunks) == text.strip()
    assert all(len(chunk) <= 80 for chunk in chunks)


def test_compact_lakh_prices_are_expanded_for_speech():
    assert speech_text("It costs INR 2.9L.") == "It costs 2 lakh 90 thousand rupees."


def test_wav_duration_is_measured_from_frames():
    assert wav_duration_seconds(_wav(bytes(8_000))) == 1.0
    assert wav_duration_seconds(b"not a wav") is None


def test_wav_duration_uses_available_frames_when_streaming_header_has_placeholder_sizes():
    audio = bytearray(_wav(bytes(8_000)))
    audio[4:8] = b"\xff\xff\xff\xff"
    data_size_offset = audio.index(b"data") + 4
    audio[data_size_offset : data_size_offset + 4] = b"\xff\xff\xff\xff"

    assert wav_duration_seconds(bytes(audio)) == 1.0


def test_synthesize_speech_stitches_wav_chunks(monkeypatch):
    calls: list[str] = []

    class SpeechApi:
        def create(self, **kwargs):
            calls.append(kwargs["input"])
            return SimpleNamespace(content=_wav(bytes([len(calls)])))

    client = SimpleNamespace(audio=SimpleNamespace(speech=SpeechApi()))
    monkeypatch.setattr("vehicle_search_agent.voice.provider._speech_clients", lambda: (client,))
    monkeypatch.setattr("vehicle_search_agent.voice.synthesis.settings.groq.tts_max_chars", 30)

    result = synthesize_speech("The first sentence is here. The second sentence is here.")

    assert len(calls) == 2
    assert all(len(chunk) <= 30 for chunk in calls)
    assert result.character_count == len("The first sentence is here. The second sentence is here.")
    with wave.open(io.BytesIO(result.audio), "rb") as reader:
        assert reader.readframes(reader.getnframes()) == b"\x01\x02"


def test_speech_request_rotates_after_rate_limit_without_moving_other_models(monkeypatch):
    calls = {"limited": 0, "working": 0}

    class TestRateLimitError(Exception):
        pass

    class RateLimitedSpeechApi:
        def create(self, **kwargs):
            calls["limited"] += 1
            raise TestRateLimitError

    class WorkingSpeechApi:
        def create(self, **kwargs):
            calls["working"] += 1
            return SimpleNamespace(content=_wav(b"\x02"))

    clients = (
        SimpleNamespace(audio=SimpleNamespace(speech=RateLimitedSpeechApi())),
        SimpleNamespace(audio=SimpleNamespace(speech=WorkingSpeechApi())),
    )
    monkeypatch.setattr(voice_provider, "RateLimitError", TestRateLimitError)
    monkeypatch.setattr(voice_provider, "_speech_clients", lambda: clients)
    monkeypatch.setattr(voice_provider, "_speech_key_indices", {})

    first = synthesize_speech("Use the second key.")
    second = synthesize_speech("Keep using the second key.")
    stt_key = voice_provider.request_with_key_rotation(
        voice_provider.settings.groq.stt_model,
        lambda client: clients.index(client),
    )

    assert calls == {"limited": 1, "working": 2}
    assert stt_key == 0
    assert voice_provider._speech_key_indices == {
        voice_provider.settings.groq.tts_model: 1,
        voice_provider.settings.groq.stt_model: 0,
    }
    for result in (first, second):
        with wave.open(io.BytesIO(result.audio), "rb") as reader:
            assert reader.readframes(reader.getnframes()) == b"\x02"
