from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "app" / "main.py"
STARTER_QUESTIONS = {
    "I need a small truck for city deliveries under ₹8 lakh",
    "Which diesel trucks can carry at least 2 tonnes?",
    "What commercial vehicles are available in Mumbai?",
}


def test_streamlit_app_renders_without_framework_error() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)

    assert not app.exception
    assert app.chat_input[0].placeholder == "Describe a vehicle need or ask a follow-up"
    assert any("Hi, I'm Vivi" in markdown.value for markdown in app.markdown)
    assert {button.label for button in app.button} >= STARTER_QUESTIONS

    app.session_state.messages = [{"role": "user", "content": "Show me a truck"}]
    app.session_state.metrics = {
        "understanding_ms": 123,
        "speech_end_to_audio_ready_ms": 455,
        "total_ms": 456,
    }
    app.session_state.usage = {
        "llm_requests": 1,
        "input_tokens": 100,
        "cached_input_tokens": 40,
        "output_tokens": 20,
        "reasoning_tokens": 5,
        "total_tokens": 120,
        "audio_input_seconds": 2.5,
        "tts_characters": 42,
        "estimated_list_cost_inr": 0.001,
    }
    app.session_state.last_tool = "search_vehicles"
    app.session_state.conversation_totals = {
        "turns": 3,
        "total_ms": 12_345,
        "llm_requests": 4,
        "input_tokens": 600,
        "cached_input_tokens": 40,
        "output_tokens": 120,
        "reasoning_tokens": 5,
        "total_tokens": 720,
        "audio_input_seconds": 2.5,
        "tts_characters": 42,
        "estimated_list_cost_inr": 0.0123,
    }
    app.run(timeout=10)

    assert not {button.label for button in app.button}.intersection(STARTER_QUESTIONS)
    assert any("Hi, I'm Vivi" in markdown.value for markdown in app.markdown)
    assert any("| **Total** | **456 ms** |" in markdown.value for markdown in app.markdown)
    assert any("Speech end to audio ready" in markdown.value for markdown in app.markdown)
    assert any("**120**" in markdown.value for markdown in app.markdown)
    assert any("Cached context tokens" in markdown.value for markdown in app.markdown)
    assert any("Reasoning tokens" in markdown.value for markdown in app.markdown)
    assert any("2.50 s" in markdown.value for markdown in app.markdown)
    assert any("12.3 s" in markdown.value for markdown in app.markdown)
    assert any("₹0.0123" in markdown.value for markdown in app.markdown)
