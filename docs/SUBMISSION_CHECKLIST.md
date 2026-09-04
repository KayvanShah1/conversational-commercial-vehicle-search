# Requirements compliance

This matrix maps each requirement to inspectable implementation or evaluation evidence. The [original specification](assignment/README.md) remains authoritative.

| Requirement | Evidence | Status |
| --- | --- | --- |
| Microphone → STT → understanding → search → response → TTS → playback | [Streamlit app](../app/main.py), [runner](../agents/src/vehicle_search_agent/runner.py), [voice pipeline](../agents/src/vehicle_search_agent/voice.py) | Met; live execution depends on provider quota and browser permission |
| At least 100 catalog rows and required fields | [Generated catalog](../data/generated/vehicles.csv) contains 1,000 listings | Met |
| Intent and required slots | [Typed tools](../agents/src/vehicle_search_agent/tools.py), [state models](../agents/src/vehicle_search_agent/models.py), visible UI state | Met |
| Strict filter enforcement | [Parameterized search and invariants](../agents/src/vehicle_search_agent/search.py) | Met |
| Grounded top-three response | [Response validation](../agents/src/vehicle_search_agent/response.py) and deterministic fallback | Met |
| Zero-result behavior | Data-tested constraint relaxation in [search](../agents/src/vehicle_search_agent/search.py) | Met and evaluated |
| Mid-conversation correction | Slot patches change only supplied or explicitly cleared values | Met and evaluated |
| Previous-result follow-up | Saved result IDs plus one bounded details lookup | Met and evaluated |
| At least 10 real-pipeline evaluation utterances | [28 core cases](../evals/datasets/agent_cases.json) and [18 variant cases](../evals/datasets/vehicle_variant_cases.json) | Met |
| Evaluation pass rate | [Evaluation report](EVALUATION.md): 28/28 core and 17/18 variants | Met; 45/46 combined (97.8%) exceeds the 90% target |
| Per-stage latency | Structured STT, understanding, search, response, TTS, and total metrics | Met |
| Speech end → first audio | [Voice latency harness](../evals/src/evals/measure_voice_latency.py) | Server-receipt-to-playable-WAV proxy; exact browser/stream boundary is stated |
| Token and estimated cost telemetry | SDK usage, voice units, successful route, and list-cost estimate | Met |
| Explainable ranking | Streamlit table exposes the numeric `RankingBreakdown` for each result | Met |
| Seven identifiable components | [Architecture](TECHNICAL_DECISIONS.md#seven-identifiable-components) and presentation | Met |
| Three decisions and rejected alternatives | [Technical decisions](TECHNICAL_DECISIONS.md) | Met |
| 100,000 conversations/month discussion | [Scale plan](TECHNICAL_DECISIONS.md#what-breaks-first-at-100000-conversations-per-month) | Met |
| README runs in under 10 minutes | [Quick start](../README.md#quick-start) and [setup guide](SETUP.md) | Met |
| Presentation PDF | [Evaluator walkthrough](../output/pdf/vivi-vehicle-search-presentation.pdf) | Met |
| External references | [Sources and acknowledgements](SOURCES.md) | Met |

## Declared limitations

- Free-tier provider capacity can be exhausted; the agent fails closed instead of inventing results.
- TTS returns a complete WAV. The reported voice metric is not first-byte streaming latency.
- INR values are reproducible public-list-price estimates, not provider invoices.
- The vehicle inventory and listing prices are synthetic demonstration data.
