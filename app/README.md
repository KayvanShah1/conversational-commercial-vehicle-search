# Vivi demo app

The app is a single-process Streamlit page for the live demonstration path:
microphone capture, transcription, agent search, grounded response, speech
synthesis, and browser audio playback. The native bottom chat composer combines
text, microphone, and send controls; both input modes use the same session.

From the repository root:

```powershell
uv run --package app streamlit run app/main.py
```

Streamlit opens <http://localhost:8501>. Browser microphone access works on
localhost.

See the repository [setup guide](../docs/SETUP.md) for credentials, catalog
loading, environment variables, and troubleshooting.
