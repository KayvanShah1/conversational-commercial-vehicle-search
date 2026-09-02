# Vivi demo app

The app is a single-process Streamlit page for the assignment's live path:
microphone capture, transcription, agent search, grounded response, speech
synthesis, and browser audio playback. Text input uses the same session and is
available as a fallback during the demo.

From the repository root:

```powershell
uv run --package app streamlit run app/main.py
```

Streamlit opens <http://localhost:8501>. Browser microphone access works on
localhost.
