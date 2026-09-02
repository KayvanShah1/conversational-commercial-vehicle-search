import io
import wave
from types import SimpleNamespace

import vehicle_search_agent.voice as voice_module
from vehicle_search_agent.voice import _text_chunks, synthesize_speech


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

    chunks = _text_chunks(text, 80)

    assert " ".join(chunks) == text.strip()
    assert all(len(chunk) <= 80 for chunk in chunks)


def test_synthesize_speech_stitches_wav_chunks(monkeypatch):
    calls: list[str] = []

    class SpeechApi:
        def create(self, **kwargs):
            calls.append(kwargs["input"])
            return SimpleNamespace(content=_wav(bytes([len(calls)])))

    client = SimpleNamespace(audio=SimpleNamespace(speech=SpeechApi()))
    monkeypatch.setattr("vehicle_search_agent.voice._speech_clients", lambda: (client,))
    monkeypatch.setattr("vehicle_search_agent.voice.settings.groq.tts_max_chars", 30)

    result = synthesize_speech("The first sentence is here. The second sentence is here.")

    assert len(calls) == 2
    assert all(len(chunk) <= 30 for chunk in calls)
    with wave.open(io.BytesIO(result.audio), "rb") as reader:
        assert reader.readframes(reader.getnframes()) == b"\x01\x02"


def test_speech_request_rotates_after_rate_limit(monkeypatch):
    class TestRateLimitError(Exception):
        pass

    class RateLimitedSpeechApi:
        def create(self, **kwargs):
            raise TestRateLimitError

    class WorkingSpeechApi:
        def create(self, **kwargs):
            return SimpleNamespace(content=_wav(b"\x02"))

    clients = (
        SimpleNamespace(audio=SimpleNamespace(speech=RateLimitedSpeechApi())),
        SimpleNamespace(audio=SimpleNamespace(speech=WorkingSpeechApi())),
    )
    monkeypatch.setattr(voice_module, "RateLimitError", TestRateLimitError)
    monkeypatch.setattr(voice_module, "_speech_clients", lambda: clients)

    result = synthesize_speech("Use the second key.")

    with wave.open(io.BytesIO(result.audio), "rb") as reader:
        assert reader.readframes(reader.getnframes()) == b"\x02"
