from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "app" / "main.py"


def test_streamlit_app_uses_native_unified_composer() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    assert "st.audio_input(" not in source
    assert "st.chat_input(" in source
    assert "accept_audio=True" in source
    assert "_render_sidebar()" in source
    assert "Compare every catalog field" in source
    assert '"Specification source": st.column_config.LinkColumn' in source
    assert 'st.container(border=True, height=390)' in source
    assert '"Brochure / specs"' in source
    assert 'lines = ["**Top match**"' in source
    assert "st.columns([3, 2]" not in source
    assert "width: 25vw !important" in source
    assert '| **Total** | **{total:,.0f} ms** |' in source
    assert "if not st.session_state.messages" not in source


def test_streamlit_app_uses_dark_theme() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")

    assert 'base = "dark"' in config


def test_streamlit_app_renders_without_framework_error() -> None:
    app = AppTest.from_file(APP_PATH).run()

    assert not app.exception
    assert app.chat_input[0].placeholder == "Describe a vehicle need or ask a follow-up"
    assert any("Hi, I'm Vivi" in markdown.value for markdown in app.markdown)

    app.session_state.messages = [{"role": "user", "content": "Show me a truck"}]
    app.session_state.metrics = {"understanding_ms": 123, "total_ms": 456}
    app.run()

    assert any("Hi, I'm Vivi" in markdown.value for markdown in app.markdown)
    assert any("| **Total** | **456 ms** |" in markdown.value for markdown in app.markdown)
