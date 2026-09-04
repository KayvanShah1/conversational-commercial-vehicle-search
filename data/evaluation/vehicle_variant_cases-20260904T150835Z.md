# Vehicle search agent evaluation

- Generated: 2026-09-04T15:08:35.796346+00:00
- Dataset: `evals/datasets/vehicle_variant_cases.json`
- Pass rate: **94.4% (17/18)**

## Mean turn telemetry

| Metric | Mean |
| --- | ---: |
| Understanding | 1,711.86 ms |
| Search | 480.73 ms |
| Response | 3,852.57 ms |
| Total | 3,467.07 ms |
| LLM Requests | 2.00 requests |
| Input Tokens | 2,780.67 tokens |
| Cached Input Tokens | 113.78 tokens |
| Output Tokens | 168.50 tokens |
| Reasoning Tokens | 99.89 tokens |
| Total Tokens | 2,949.17 tokens |
| Estimated List Cost INR | 0.0466 INR |

## Cases

| Case | Action | Model route | Result | Total ms | Tokens | Est. INR | Problems |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| variant_light_mini_reefer_cng | search | groq-key-1/openai/gpt-oss-120b | PASS | 5309.83 | 1787 | 0.0299 | - |
| variant_light_pickup_open_diesel | search | groq-key-2/openai/gpt-oss-120b | PASS | 1596.35 | 1788 | 0.0300 | - |
| suggest_more_options | search | groq-key-2/openai/gpt-oss-120b | PASS | 966.31 | 2020 | 0.0333 | - |
| all_option_weights | details | groq-key-2/openai/gpt-oss-120b | PASS | 3118.06 | 5129 | 0.0916 | - |
| all_details_first_vehicle | details | groq-key-3/openai/gpt-oss-120b | PASS | 10191.58 | 5844 | 0.0934 | - |
| variant_intermediate_rigid_box | search | groq-key-2/openai/gpt-oss-120b | PASS | 1130.09 | 1816 | 0.0316 | - |
| variant_medium_rigid_container | search | groq-key-2/openai/gpt-oss-120b | PASS | 1036.57 | 1801 | 0.0308 | - |
| attribute_price_and_year | details | groq-key-2/openai/gpt-oss-120b | PASS | 4195.79 | 4130 | 0.0639 | - |
| attribute_mileage_and_condition | details | groq-key-3/openai/gpt-oss-120b | PASS | 14466.37 | 4474 | 0.0677 | - |
| attribute_payload_and_gvw | details | groq-key-3/openai/gpt-oss-120b | PASS | 1811.37 | 5035 | 0.0797 | - |
| attribute_fuel_body_city_papers | details | groq-key-1/openai/gpt-oss-20b | PASS | 10133.4 | 5297 | 0.0637 | - |
| attribute_cheapest_comparison | conversation | groq-key-1/openai/gpt-oss-20b | FAIL | 1024.73 | 2984 | 0.0292 | action=conversation; response_missing_required_text |
| variant_heavy_rigid_tipper | search | groq-key-2/openai/gpt-oss-120b | PASS | 993.01 | 1812 | 0.0313 | - |
| variant_heavy_rigid_flatbed | search | groq-key-2/openai/gpt-oss-120b | PASS | 1644.21 | 1802 | 0.0307 | - |
| variant_medium_rigid_tanker | search | groq-key-2/openai/gpt-oss-120b | PASS | 1185.75 | 1791 | 0.0301 | - |
| budget_price_range | search | groq-key-2/openai/gpt-oss-120b | PASS | 1094.46 | 1807 | 0.0310 | - |
| weight_two_tonne_payload | search | groq-key-2/openai/gpt-oss-120b | PASS | 1313.09 | 1792 | 0.0301 | - |
| general_payload_vs_gvw | conversation | groq-key-2/openai/gpt-oss-120b | PASS | 1196.32 | 1976 | 0.0408 | - |

## Cost method

Equivalent list-price cost uses the successful model route for each LLM call. Actual free-tier spend may be zero. Voice turns additionally include STT audio duration and TTS characters.
The USD/INR conversion assumption is documented in `docs/TECHNICAL_DECISIONS.md`.
