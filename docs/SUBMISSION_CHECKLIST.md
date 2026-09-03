# Assignment compliance checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Microphone to STT to understanding to search to response to TTS to playback | `app/main.py`, `runner.py`, `voice.py` | Implemented; final live run depends on provider quota and browser permission |
| At least 100 catalog rows and required fields | `data/generated/vehicles.csv` has 1,000 listings plus its header | Met |
| Intent and required slots | Three typed tools, `SlotPatch`, visible Streamlit state | Met |
| Strict filter enforcement | Parameterized SQL plus `_matches` invariant | Met |
| Grounded top-three response | `GroundedResponse`, numeric/fact validation, deterministic fallback | Met |
| Zero results | Deterministic no-result response with one data-tested relaxation | Met |
| Mid-conversation correction | Slot patch changes only supplied/cleared fields | Met and evaluated |
| Previous-result follow-up | Result IDs in state plus one details lookup | Met and evaluated |
| At least 10 real-pipeline evaluation utterances with expected filters | 27 core cases and 18 focused variant cases under `evals/` | Met |
| Pass rate | Latest live runs: 27/27 core and 17/18 variant cases (94.4%); one semantic-check vocabulary miss, no behavior mismatch | Met: both exceed 90% |
| Per-stage latency | Structured metrics/logs for STT, understanding, search, response, TTS, and total; latest core means are documented | Implemented |
| Speech end to first audio | `speech_end_to_audio_ready_ms` is shown per voice turn and logged | Implemented as a server-receipt-to-playable-WAV proxy; exact browser speech-stop/first-byte needs a custom streaming client |
| Token and estimated cost telemetry | SDK request/input/cached/output/reasoning/total tokens plus voice duration/characters and route-aware list-cost estimate | Implemented |
| Explainable ranking | UI table exposes the numeric per-listing ranking components | Implemented |
| Seven-component architecture diagram | Root README and presentation slide 3 | Met |
| Three decisions and rejected alternatives | `docs/TECHNICAL_DECISIONS.md` and presentation slide 7 | Met |
| 100,000 conversations/month answer | `docs/TECHNICAL_DECISIONS.md` and presentation slide 8 | Met |
| README runs in under 10 minutes | Root README setup and demo path | Met |
| Presentation slides in PDF | `output/pdf/vivi-vehicle-search-presentation.pdf` | Met |
| Cite external sources | `docs/SOURCES.md` | Met |

## Submission risks to state, not hide

1. Free-tier model pools can all return HTTP 429; the UI fails closed and asks
   for a retry instead of inventing a vehicle.
2. The TTS endpoint returns complete WAV responses. The current latency metric
   is therefore speech-end-to-playable-audio, not first streamed audio bytes.
3. The INR figure is an equivalent public-list-price estimate, not a provider
   billing amount. Free-tier spend can be zero, and database/hosting costs are
   outside the turn estimate.
