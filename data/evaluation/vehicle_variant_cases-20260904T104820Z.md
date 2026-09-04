# Vehicle search agent evaluation

- Generated: 2026-09-04T10:48:20.560878+00:00
- Dataset: `evals/datasets/vehicle_variant_cases.json`
- Pass rate: **100.0% (4/4)**

## Mean turn telemetry

| Metric | Mean |
| --- | ---: |
| Understanding | 1,116.52 ms |
| Search | 1,394.91 ms |
| Response | 5,019.69 ms |
| Total | 5,075.53 ms |
| LLM Requests | 1.75 requests |
| Input Tokens | 3,597.50 tokens |
| Cached Input Tokens | 768.00 tokens |
| Output Tokens | 264.50 tokens |
| Reasoning Tokens | 167.00 tokens |
| Total Tokens | 3,862.00 tokens |
| Estimated List Cost INR | 0.0666 INR |

## Cases

| Case | Action | Model route | Result | Total ms | Tokens | Est. INR | Problems |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| variant_light_pickup_open_diesel | search | groq-key-1/openai/gpt-oss-120b | PASS | 6014.56 | 1790 | 0.0301 | - |
| suggest_more_options | search | groq-key-1/openai/gpt-oss-120b | PASS | 1067.68 | 1976 | 0.0307 | - |
| all_option_weights | details | groq-key-1/openai/gpt-oss-120b | PASS | 2893.46 | 5440 | 0.1038 | - |
| all_details_first_vehicle | details | groq-key-2/openai/gpt-oss-120b | PASS | 10326.41 | 6242 | 0.1019 | - |

## Cost method

Equivalent list-price cost uses the successful model route for each LLM call. Actual free-tier spend may be zero. Voice turns additionally include STT audio duration and TTS characters.
The USD/INR conversion assumption is documented in `docs/TECHNICAL_DECISIONS.md`.
