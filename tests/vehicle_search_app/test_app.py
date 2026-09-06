from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest
from vehicle_search_agent.models import (
    RankedVehicle,
    RankingBreakdown,
    SearchFilters,
    VehicleRecord,
    VehicleSearchResult,
)
from vehicle_search_agent.response import GroundedResponse

ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "app" / "main.py"
STARTER_QUESTIONS = {
    "I need a small truck for city deliveries under ₹8 lakh",
    "Which diesel trucks can carry at least 2 tonnes?",
    "What commercial vehicles are available in Mumbai?",
}


def test_zero_result_response_is_rendered_as_one_sentence(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "app"))
    from components import display_response

    fallback = "I couldn't find an exact match. We could try relaxing the budget constraint."
    grounded = GroundedResponse(
        fallback=fallback,
        facts=("I couldn't find an exact match.", "We could try relaxing the budget constraint."),
        checks=(("I couldn't find an exact match.",), ("We could try relaxing the budget constraint.",)),
    )
    result = SimpleNamespace(
        action=SimpleNamespace(value="search"),
        last_result_ids=[],
        spoken_response=fallback,
    )
    session = SimpleNamespace(context=SimpleNamespace(grounded_response=grounded))

    assert display_response(result, session) == fallback


def test_streamlit_app_renders_without_framework_error() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)

    assert not app.exception
    assert app.chat_input[0].placeholder == "Describe a vehicle need or ask a follow-up"
    assert any("Hi, I'm Vivi" in markdown.value for markdown in app.markdown)
    assert {button.label for button in app.button} >= STARTER_QUESTIONS
    assert any(button.label == "Start new chat" and button.key == "new_chat" for button in app.button)

    app.session_state.messages = [
        {"role": "user", "content": "Which cities do you operate in?"},
        {
            "role": "assistant",
            "content": "We have listings in Ahmedabad and Mumbai.",
            "tool": "list_catalog_options",
        },
    ]
    app.session_state.metrics = {
        "understanding_ms": 123,
        "recording_received_to_audio_ready_ms": 455,
        "total_ms": 456,
    }
    app.session_state.usage = {
        "llm_requests": 1,
        "input_tokens": 100,
        "cached_input_tokens": 40,
        "output_tokens": 20,
        "reasoning_tokens": 5,
        "total_tokens": 120,
        "audio_input_seconds": 2.5,
        "tts_characters": 42,
        "estimated_llm_list_cost_inr": 0.0004,
        "estimated_stt_list_cost_inr": 0.0001,
        "estimated_tts_list_cost_inr": 0.0005,
        "estimated_list_cost_inr": 0.001,
    }
    app.session_state.conversation_totals = {
        "turns": 3,
        "total_ms": 12_345,
        "llm_requests": 4,
        "input_tokens": 600,
        "cached_input_tokens": 40,
        "output_tokens": 120,
        "reasoning_tokens": 5,
        "total_tokens": 720,
        "audio_input_seconds": 2.5,
        "tts_characters": 42,
        "estimated_llm_list_cost_inr": 0.005,
        "estimated_stt_list_cost_inr": 0.0013,
        "estimated_tts_list_cost_inr": 0.006,
        "estimated_list_cost_inr": 0.0123,
    }
    app.session_state.last_search_result = VehicleSearchResult(
        executed_filters=SearchFilters(budget_max=800_000, purpose="city_delivery"),
        changed_fields=[],
        vehicles=[
            RankedVehicle(
                vehicle=VehicleRecord(
                    listing_id="VEH-TEST",
                    make="Mahindra",
                    model="Jeeto Strong Diesel",
                    year=2024,
                    price_inr=440_000,
                    km_driven=29_919,
                    fuel="Diesel",
                    payload_kg=815,
                    payload_is_estimated=True,
                    gvw_kg=1_605,
                    vehicle_category="mini_truck",
                    weight_class="light",
                    body_type="box",
                    axle_count=2,
                    city="Chennai",
                    papers_verified=True,
                    condition="excellent",
                    purpose_tags=["city_delivery"],
                    spec_source_url="https://example.com/jeeto",
                ),
                score=RankingBreakdown(
                    purpose=1,
                    papers_verified=1,
                    budget=1,
                    km_driven=1,
                    condition=1,
                    year=1,
                    total=6,
                ),
            )
        ],
        total_matches=1,
        search_ms=10,
    )
    app.run(timeout=10)

    assert not {button.label for button in app.button}.intersection(STARTER_QUESTIONS)
    assert any("Hi, I'm Vivi" in markdown.value for markdown in app.markdown)
    assert any("Tool used: `list_catalog_options`" in caption.value for caption in app.caption)
    assert any("| Recording received → audio ready | 455 ms |" in markdown.value for markdown in app.markdown)
    assert not any("Voice processing total" in markdown.value for markdown in app.markdown)
    assert any("**120**" in markdown.value for markdown in app.markdown)
    assert any("Cached context tokens" in markdown.value for markdown in app.markdown)
    assert any("Reasoning tokens" in markdown.value for markdown in app.markdown)
    assert any("| **Total LLM tokens** | **120** | **₹0.0004** |" in markdown.value for markdown in app.markdown)
    assert any("| STT audio | 2.50 s | ₹0.0001 |" in markdown.value for markdown in app.markdown)
    assert any("| TTS output | 42 characters | ₹0.0005 |" in markdown.value for markdown in app.markdown)
    assert any("| **Turn total** |  | **₹0.0010** |" in markdown.value for markdown in app.markdown)
    assert any("12.3 s" in markdown.value for markdown in app.markdown)
    assert any("| LLM tokens | 720 | ₹0.0050 |" in markdown.value for markdown in app.markdown)
    assert any("| STT audio | 2.50 s | ₹0.0013 |" in markdown.value for markdown in app.markdown)
    assert any("| TTS output | 42 characters | ₹0.0060 |" in markdown.value for markdown in app.markdown)
    assert any("| **Conversation total** |  | **₹0.0123** |" in markdown.value for markdown in app.markdown)
    assert any("weighted signals below" in caption.value for caption in app.caption)
    assert any("Vivi may infer purpose and vehicle size" in caption.value for caption in app.caption)
    assert any(
        "Purpose fit" in dataframe.value.columns and dataframe.value.iloc[0]["Purpose fit"] == "30%"
        for dataframe in app.dataframe
    )
    assert any("Mahindra Jeeto Strong Diesel" in markdown.value for markdown in app.markdown)
    assert any(metric.label == "Est. payload" for metric in app.metric)
    assert any(metric.value == "815 kg" for metric in app.metric)

    app.session_state.metrics = {"understanding_ms": 123, "total_ms": 456}
    app.run(timeout=10)

    assert any("| **Turn total** | **456 ms** |" in markdown.value for markdown in app.markdown)
