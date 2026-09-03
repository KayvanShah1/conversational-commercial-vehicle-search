# Sources and acknowledgements

The implementation is original to this project. It uses the following
libraries, hosted models, and official documentation:

- [OpenAI Agents SDK: agents and tool-result behavior](https://openai.github.io/openai-agents-python/agents/)
  for the bounded agent loop, typed function tools, sessions, and tracing.
- [OpenAI Agents SDK: function tools](https://openai.github.io/openai-agents-python/tools/)
  for schema generation and tool-call validation.
- [OpenAI Agents SDK: usage](https://openai.github.io/openai-agents-python/usage/)
  for request, input, cached-input, output, reasoning, and total token counts.
- [Streamlit `st.chat_input`](https://docs.streamlit.io/develop/api-reference/chat/st.chat_input)
  for a single text composer with built-in browser microphone capture at a
  speech-recognition-oriented 16 kHz sample rate.
- [Groq speech-to-text documentation](https://console.groq.com/docs/speech-to-text)
  for Whisper transcription formats, limits, and audio guidance.
- [Groq Orpheus text-to-speech documentation](https://console.groq.com/docs/text-to-speech/orpheus)
  for the 200-character request limit, voices, and WAV response format. Vivi
  splits longer text into sequential requests and stitches compatible WAV data
  in application code; this is not the provider's batch API.
- [Groq supported models and pricing](https://console.groq.com/docs/models)
  for the GPT-OSS and Whisper list rates used by the cost estimator.
- [FBIL](https://www.fbil.org.in/)
  for the 25 August 2026 USD/INR reference rate; code rounds 95.4254 to 95.43.
- [MotherDuck Python connection overview](https://motherduck.com/glossary/motherduck/)
  for the `md:` connection protocol.
- [MotherDuck read-only agent guidance](https://motherduck.com/blog/langchain-sql-agent-duckdb-motherduck/)
  for enforcing read-only access at the connection or token boundary rather
  than relying on a prompt.
- [DuckDB Python API](https://duckdb.org/docs/stable/clients/python/overview)
  for parameterized queries and connection lifecycle.

Models are configured by identifier in `example.env`. Availability, pricing,
and free-tier quotas are provider-controlled and may change after submission.
