from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"


def test_streamlit_app_has_required_demo_controls() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    assert 'chat_col, info_col = st.columns([3, 2]' in source
    assert 'st.audio_input(' in source
    assert 'st.chat_input("Message Vivi"' in source
    assert 'class="hud-grid"' in source
    assert "All catalog fields" in source


def test_streamlit_app_renders_without_framework_error() -> None:
    app = AppTest.from_file(APP_PATH).run()

    assert not app.exception
    assert app.chat_input[0].placeholder == "Message Vivi"
    assert any("Hi, I'm Vivi" in markdown.value for markdown in app.markdown)
