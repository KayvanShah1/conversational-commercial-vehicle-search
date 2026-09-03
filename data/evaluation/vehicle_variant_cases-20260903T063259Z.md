# Vehicle search agent evaluation

- Generated: 2026-09-03T06:32:59.901216+00:00
- Dataset: `evals/vehicle_variant_cases.json`
- Pass rate: **100.0% (2/2)**

## Mean turn telemetry

| Metric | Mean |
| --- | ---: |
| Understanding | 1,137.45 ms |
| Search | 2,521.24 ms |
| Response | 873.64 ms |
| Total | 4,144.05 ms |
| LLM Requests | 2.00 requests |
| Input Tokens | 2,769.50 tokens |
| Cached Input Tokens | 256.00 tokens |
| Output Tokens | 113.00 tokens |
| Reasoning Tokens | 45.50 tokens |
| Total Tokens | 2,882.50 tokens |
| Estimated List Cost INR | 0.0461 INR |

## Cases

| Case | Action | Model route | Result | Total ms | Tokens | Est. INR | Problems |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| variant_medium_rigid_container | search | groq-key-2/openai/gpt-oss-120b | PASS | 5877.9 | 1728 | 0.0287 | - |
| attribute_fuel_body_city_papers | details | groq-key-2/openai/gpt-oss-120b | PASS | 2410.19 | 4037 | 0.0635 | - |

## Cost method

Equivalent list-price cost uses the successful model route for each LLM call. Actual free-tier spend may be zero. Voice turns additionally include STT audio duration and TTS characters.
The USD/INR conversion assumption is documented in `docs/TECHNICAL_DECISIONS.md`.
