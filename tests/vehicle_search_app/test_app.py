from pathlib import Path


def test_streamlit_app_has_required_demo_controls() -> None:
    source = Path("app/main.py").read_text(encoding="utf-8")

    assert 'st.audio_input("Record your requirement in English or Hinglish")' in source
    assert 'st.chat_input("Type your requirement or a follow-up question")' in source
    assert 'st.subheader("Current understanding")' in source
    assert 'st.subheader("Latency")' in source
    assert 'st.subheader("Play response")' in source
