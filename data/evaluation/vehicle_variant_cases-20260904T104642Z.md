# Vehicle search agent evaluation

- Generated: 2026-09-04T10:46:42.251441+00:00
- Dataset: `evals/datasets/vehicle_variant_cases.json`
- Pass rate: **75.0% (3/4)**

## Mean turn telemetry

| Metric | Mean |
| --- | ---: |
| Understanding | 2,485.75 ms |
| Search | 1,484.52 ms |
| Response | 5,205.88 ms |
| Total | 6,611.05 ms |
| LLM Requests | 1.75 requests |
| Input Tokens | 3,450.00 tokens |
| Cached Input Tokens | 256.00 tokens |
| Output Tokens | 199.50 tokens |
| Reasoning Tokens | 104.50 tokens |
| Total Tokens | 3,649.50 tokens |
| Estimated List Cost INR | 0.0608 INR |

## Cases

| Case | Action | Model route | Result | Total ms | Tokens | Est. INR | Problems |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| variant_light_pickup_open_diesel | search | groq-key-1/openai/gpt-oss-120b | PASS | 6280.51 | 1793 | 0.0303 | - |
| suggest_more_options | search | groq-key-1/openai/gpt-oss-120b | PASS | 1128.52 | 1979 | 0.0307 | - |
| all_option_weights | details | groq-key-1/openai/gpt-oss-120b | PASS | 2355.59 | 5068 | 0.0909 | - |
| all_details_first_vehicle | details | groq-key-2/openai/gpt-oss-120b | FAIL | 16679.6 | 5758 | 0.0913 | response_missing_expected_concept |

## Cost method

Equivalent list-price cost uses the successful model route for each LLM call. Actual free-tier spend may be zero. Voice turns additionally include STT audio duration and TTS characters.
The USD/INR conversion assumption is documented in `docs/TECHNICAL_DECISIONS.md`.
