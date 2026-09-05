from vehicle_search_agent.pricing import llm_list_cost_usd


def test_llm_list_cost_uses_input_and_output_rates():
    assert llm_list_cost_usd("openai/gpt-oss-120b", 1_000_000, 1_000_000) == 0.75
    assert llm_list_cost_usd("unknown-model", 100, 100) is None
