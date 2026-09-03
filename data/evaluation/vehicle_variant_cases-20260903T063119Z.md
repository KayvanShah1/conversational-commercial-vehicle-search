# Vehicle search agent evaluation

- Generated: 2026-09-03T06:31:19.404079+00:00
- Dataset: `evals/vehicle_variant_cases.json`
- Pass rate: **94.4% (17/18)**

## Mean turn telemetry

| Metric | Mean |
| --- | ---: |
| Understanding | 1,680.80 ms |
| Search | 797.50 ms |
| Response | 4,007.81 ms |
| Total | 4,032.36 ms |
| LLM Requests | 2.06 requests |
| Input Tokens | 2,867.56 tokens |
| Cached Input Tokens | 298.67 tokens |
| Output Tokens | 180.17 tokens |
| Reasoning Tokens | 110.78 tokens |
| Total Tokens | 3,047.72 tokens |
| Estimated List Cost INR | 0.0467 INR |

## Cases

| Case | Action | Model route | Result | Total ms | Tokens | Est. INR | Problems |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| variant_light_mini_reefer_cng | search | groq-key-2/openai/gpt-oss-120b | PASS | 6848.27 | 1752 | 0.0300 | - |
| variant_light_pickup_open_diesel | search | groq-key-2/openai/gpt-oss-120b | PASS | 13462.51 | 1734 | 0.0291 | - |
| suggest_more_options | search | groq-key-2/openai/gpt-oss-120b | PASS | 1478.33 | 1920 | 0.0299 | - |
| all_option_weights | details | groq-key-2/openai/gpt-oss-120b | PASS | 2199.99 | 4640 | 0.0779 | - |
| all_details_first_vehicle | details | groq-key-3/openai/gpt-oss-120b | PASS | 13048.73 | 5360 | 0.0879 | - |
| variant_intermediate_rigid_box | search | groq-key-1/openai/gpt-oss-120b | PASS | 1291.92 | 1762 | 0.0306 | - |
| variant_medium_rigid_container | search | groq-key-2/openai/gpt-oss-120b | PASS | 1034.66 | 1756 | 0.0303 | - |
| attribute_price_and_year | details | groq-key-2/openai/gpt-oss-120b | PASS | 1411.04 | 4025 | 0.0621 | - |
| attribute_mileage_and_condition | details | groq-key-3/openai/gpt-oss-120b | PASS | 9331.52 | 4369 | 0.0662 | - |
| attribute_payload_and_gvw | details | groq-key-3/openai/gpt-oss-120b | PASS | 1727.04 | 5039 | 0.0832 | - |
| attribute_fuel_body_city_papers | details | groq-key-1/openai/gpt-oss-20b | FAIL | 9607.89 | 5172 | 0.0598 | response_missing_expected_concept |
| attribute_cheapest_comparison | details | groq-key-1/openai/gpt-oss-20b | PASS | 2124.66 | 6666 | 0.0652 | - |
| variant_heavy_rigid_tipper | search | groq-key-2/openai/gpt-oss-120b | PASS | 988.19 | 1753 | 0.0301 | - |
| variant_heavy_rigid_flatbed | search | groq-key-2/openai/gpt-oss-120b | PASS | 2568.59 | 1768 | 0.0309 | - |
| variant_medium_rigid_tanker | search | groq-key-2/openai/gpt-oss-120b | PASS | 1423.04 | 1750 | 0.0299 | - |
| budget_price_range | search | groq-key-2/openai/gpt-oss-120b | PASS | 1519.39 | 1747 | 0.0297 | - |
| weight_two_tonne_payload | search | groq-key-2/openai/gpt-oss-120b | PASS | 1252.08 | 1736 | 0.0291 | - |
| general_payload_vs_gvw | conversation | groq-key-2/openai/gpt-oss-120b | PASS | 1264.72 | 1910 | 0.0392 | - |

## Cost method

Equivalent list-price cost uses the successful model route for each LLM call. Actual free-tier spend may be zero. Voice turns additionally include STT audio duration and TTS characters.
The USD/INR conversion assumption is documented in `docs/TECHNICAL_DECISIONS.md`.
