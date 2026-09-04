from vehicle_search_agent.models import (
    DetailField,
    RankedVehicle,
    RankingBreakdown,
    SearchFilters,
    VehicleRecord,
    VehicleSearchResult,
)
from vehicle_search_agent.response import (
    GroundedResponse,
    conversational_response,
    details_response,
    natural_response,
    search_response,
)


def _priced_vehicle(listing_id: str, price: int) -> VehicleRecord:
    return VehicleRecord(
        listing_id=listing_id,
        make="Tata",
        model=listing_id,
        year=2022,
        price_inr=price,
        km_driven=20_000,
        fuel="Diesel",
        payload_kg=2_000,
        gvw_kg=4_000,
        vehicle_category="pickup",
        weight_class="light",
        body_type="open",
        axle_count=2,
        city="Pune",
        papers_verified=True,
        condition="good",
        purpose_tags=["city_delivery"],
        spec_source_url="https://example.com",
    )


def _ranked(vehicle: VehicleRecord, total: float) -> RankedVehicle:
    score = RankingBreakdown(
        purpose=0,
        papers_verified=0,
        budget=0,
        mileage=0,
        condition=0,
        year=0,
        total=total,
    )
    return RankedVehicle(vehicle=vehicle, score=score)


def test_search_response_identifies_the_first_ranked_result_as_top_match():
    result = VehicleSearchResult(
        executed_filters=SearchFilters(),
        changed_fields=[],
        vehicles=[_ranked(_priced_vehicle("First", 800_000), 2), _ranked(_priced_vehicle("Second", 700_000), 1)],
        total_matches=2,
        search_ms=10,
    )

    response = search_response(result)

    assert response.fallback.startswith("Top match: Tata First")
    assert "Other options: Tata Second" in response.fallback


def test_general_advice_can_use_numbered_prose_but_not_vehicle_measurements():
    advice = conversational_response("1. Choose based on your route. 2. Compare fuel access.", first_turn=False)
    blocked = conversational_response("This truck carries 1500 kg.", first_turn=False)

    assert advice.startswith("1.")
    assert blocked == "I can help with commercial-vehicle searches and general questions about choosing one."


def test_greeting_is_catalog_neutral_even_if_model_mentions_a_van():
    response = conversational_response(
        "I can help you find a truck or van.",
        first_turn=True,
        user_input="yo",
    )

    assert response == "Hey, I'm Vivi. Tell me what you need to transport, your budget, and where you're looking."


def test_cheapest_comparison_is_explicit_and_grounded():
    response = details_response(
        [_priced_vehicle("Costly", 1_000_000), _priced_vehicle("Cheap", 800_000)],
        [DetailField.price],
        "Which is cheapest?",
    )

    assert response.fallback.endswith("Cheapest: Tata Cheap at INR 8L.")


def test_vehicle_source_link_is_returned_as_a_grounded_detail():
    vehicle = _priced_vehicle("Brochure", 1_000_000)

    response = details_response([vehicle], [DetailField.spec_source_url], "Does it have a brochure?")

    assert response.fallback == "The specification source for Tata Brochure is https://example.com."
    assert response.checks == (("Tata Brochure", "https://example.com"),)
    assert "[View manufacturer specifications](https://example.com)" in response.display_markdown


def test_all_details_have_natural_speech_and_structured_display():
    vehicle = _priced_vehicle("Ace Gold", 560_000)
    response = details_response([vehicle], list(DetailField))

    assert "Tata Ace Gold is a 2022 pickup and has an open body." in response.fallback
    assert "It costs INR 5.6L, has covered 20,000 km, and runs on Diesel." in response.fallback
    assert "- **Payload:** 2,000 kg" in response.display_markdown
    assert "- **GVW:** 4,000 kg" in response.display_markdown

    multiple = details_response([vehicle, vehicle.model_copy(update={"listing_id": "second"})], list(DetailField))
    assert multiple.fallback.startswith("I found 2 matching listings.")
    assert multiple.fallback.endswith("The full specifications and source links are shown on screen.")


def test_accepts_natural_framing_around_unchanged_facts():
    fact = "Tata Ace Gold, INR 5.6L, verified papers"
    grounded = GroundedResponse(
        fallback=f"I found this match: {fact}.",
        facts=(fact,),
        checks=(("Tata Ace Gold", "INR 5.6L", "verified"),),
    )
    response = natural_response(
        "Good news - Tata Ace Gold is available for 5.6 L with verified papers.",
        grounded,
        first_turn=False,
    )

    assert response.startswith("Good news")


def test_rejects_a_changed_catalog_fact():
    fact = "Tata Ace Gold, INR 5.6L, verified papers"
    fallback = f"I found this match: {fact}."
    grounded = GroundedResponse(
        fallback=fallback,
        facts=(fact,),
        checks=(("Tata Ace Gold", "INR 5.6L", "verified"),),
    )

    response = natural_response(
        "I found Tata Ace Gold, INR 6.5L, verified papers.",
        grounded,
        first_turn=False,
    )

    assert response == fallback


def test_accepts_one_shared_reason_for_all_results_and_adds_a_warm_intro():
    facts = (
        "Tata Ace Gold, INR 5.6L, verified papers",
        "Mahindra Jeeto, INR 4.4L, verified papers",
    )
    grounded = GroundedResponse(
        fallback="I found these matches: " + "; ".join(facts) + ".",
        facts=facts,
        checks=(("Tata Ace Gold", "INR 5.6L"), ("Mahindra Jeeto", "INR 4.4L"), ("verified",)),
    )

    response = natural_response(
        "Two options stand out: Tata Ace Gold for ₹5.6 L and Mahindra Jeeto for ₹4.4 L, both verified.",
        grounded,
        first_turn=True,
    )

    assert response.startswith("Hi, I'm Vivi. I'll help you find the right used truck.")
    assert "both verified" in response
