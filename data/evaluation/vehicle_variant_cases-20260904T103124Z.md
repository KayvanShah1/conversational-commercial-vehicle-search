# Vehicle search agent evaluation

- Generated: 2026-09-04T10:31:24.612681+00:00
- Dataset: `evals/datasets/vehicle_variant_cases.json`
- Pass rate: **88.9% (16/18)**

## Mean turn telemetry

| Metric | Mean |
| --- | ---: |
| Understanding | 1,979.98 ms |
| Search | 550.36 ms |
| Response | 3,899.75 ms |
| Total | 4,074.41 ms |
| LLM Requests | 1.50 requests |
| Input Tokens | 2,978.17 tokens |
| Cached Input Tokens | 867.56 tokens |
| Output Tokens | 154.72 tokens |
| Reasoning Tokens | 78.89 tokens |
| Total Tokens | 3,132.89 tokens |
| Estimated List Cost INR | 0.0515 INR |

## Cases

| Case | Action | Model route | Result | Total ms | Tokens | Est. INR | Problems |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| variant_light_mini_reefer_cng | search | groq-key-1/openai/gpt-oss-120b | PASS | 7015.16 | 1790 | 0.0300 | - |
| variant_light_pickup_open_diesel | search | groq-key-1/openai/gpt-oss-120b | PASS | 1757.02 | 1793 | 0.0303 | - |
| suggest_more_options | search | groq-key-1/openai/gpt-oss-120b | PASS | 837.71 | 1979 | 0.0307 | - |
| all_option_weights | details | groq-key-1/openai/gpt-oss-120b | FAIL | 3141.23 | 5317 | 0.0980 | response_missing_required_text |
| all_details_first_vehicle | details | groq-key-1/openai/gpt-oss-120b | FAIL | 8629.48 | 6444 | 0.1025 | response_missing_expected_concept |
| variant_intermediate_rigid_box | search | groq-key-1/openai/gpt-oss-120b | PASS | 809.58 | 1816 | 0.0316 | - |
| variant_medium_rigid_container | search | groq-key-1/openai/gpt-oss-120b | PASS | 4003.79 | 1772 | 0.0291 | - |
| attribute_price_and_year | details | groq-key-2/openai/gpt-oss-120b | PASS | 15423.51 | 4053 | 0.0624 | - |
| attribute_mileage_and_condition | details | groq-key-2/openai/gpt-oss-120b | PASS | 1599.75 | 4393 | 0.0664 | - |
| attribute_payload_and_gvw | details | groq-key-2/openai/gpt-oss-120b | PASS | 3675.75 | 4856 | 0.0750 | - |
| attribute_fuel_body_city_papers | details | groq-key-2/openai/gpt-oss-120b | PASS | 8811.69 | 5305 | 0.0803 | - |
| attribute_cheapest_comparison | details | groq-key-3/openai/gpt-oss-120b | PASS | 9681.6 | 5708 | 0.0857 | - |
| variant_heavy_rigid_tipper | search | groq-key-1/openai/gpt-oss-120b | PASS | 1023.77 | 1803 | 0.0308 | - |
| variant_heavy_rigid_flatbed | search | groq-key-1/openai/gpt-oss-120b | PASS | 1215.9 | 1815 | 0.0315 | - |
| variant_medium_rigid_tanker | search | groq-key-1/openai/gpt-oss-120b | PASS | 1436.67 | 1819 | 0.0317 | - |
| budget_price_range | search | groq-key-1/openai/gpt-oss-120b | PASS | 1302.6 | 1805 | 0.0309 | - |
| weight_two_tonne_payload | search | groq-key-1/openai/gpt-oss-120b | PASS | 1493.56 | 1800 | 0.0306 | - |
| general_payload_vs_gvw | conversation | groq-key-1/openai/gpt-oss-120b | PASS | 1480.55 | 2124 | 0.0493 | - |

## Cost method

Equivalent list-price cost uses the successful model route for each LLM call. Actual free-tier spend may be zero. Voice turns additionally include STT audio duration and TTS characters.
The USD/INR conversion assumption is documented in `docs/TECHNICAL_DECISIONS.md`.
