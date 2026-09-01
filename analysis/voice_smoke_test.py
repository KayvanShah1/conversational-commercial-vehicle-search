from rich.pretty import pprint
from vehicle_search_agent.settings import settings
from vehicle_search_agent.voice import synthesize_speech, transcribe_audio

SMOKE_TEST_DIR = settings.data_dir / "smoke_test"
if not SMOKE_TEST_DIR.exists():
    SMOKE_TEST_DIR.mkdir(parents=True, exist_ok=True)

STT_AUDIO_PATH = SMOKE_TEST_DIR / "vanilla-ice-cream.wav"
TTS_TEXT = "I like eating avacodo banana smoothie with nuts and cardamom."
TTS_AUDIO_PATH = SMOKE_TEST_DIR / "avacodo-banana-smoothie.wav"


def main() -> None:
    if not STT_AUDIO_PATH.is_file():
        raise FileNotFoundError(f"STT audio file not found: {STT_AUDIO_PATH}")

    audio_bytes = STT_AUDIO_PATH.read_bytes()
    transcription = transcribe_audio(audio_bytes, filename=STT_AUDIO_PATH.name)

    pprint("STT smoke test")
    pprint(f"audio_file={STT_AUDIO_PATH}")
    pprint(f"model={settings.groq.stt_model}")
    pprint(f"duration_ms={transcription.duration_ms:.2f}")
    pprint(f"transcription={transcription.text}")

    speech = synthesize_speech(TTS_TEXT)
    TTS_AUDIO_PATH.write_bytes(speech.audio)

    pprint("TTS smoke test")
    pprint(f"text={TTS_TEXT}")
    pprint(f"model={settings.groq.tts_model}")
    pprint(f"voice={settings.groq.tts_voice}")
    pprint(f"duration_ms={speech.duration_ms:.2f}")
    pprint(f"audio_file={TTS_AUDIO_PATH}")
    pprint(f"audio_bytes={len(speech.audio)}")


if __name__ == "__main__":
    main()
