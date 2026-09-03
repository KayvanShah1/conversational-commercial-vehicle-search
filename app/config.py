SLOT_LABELS = {
    "budget_min": "Minimum budget",
    "budget_max": "Maximum budget",
    "body_type": "Body type",
    "fuel": "Fuel",
    "city": "City",
    "purpose": "Purpose",
    "vehicle_category": "Category",
    "weight_class": "Size",
    "make": "Make",
    "model": "Model",
    "payload_min_kg": "Minimum payload",
    "gvw_min_kg": "Minimum GVW",
    "papers_verified": "Verified papers",
}

METRIC_LABELS = {
    "stt_ms": "STT",
    "understanding_ms": "Understanding",
    "search_ms": "Search",
    "response_ms": "Response",
    "tts_ms": "TTS",
    "speech_end_to_audio_ready_ms": "Speech end to audio ready",
    "total_ms": "Total",
}

TOOL_NAMES = {
    "conversation": "No tool",
    "search": "search_vehicles",
    "details": "get_vehicle_details",
    "catalog_options": "list_catalog_options",
}

STARTER_QUESTIONS = (
    "I need a small truck for city deliveries under ₹8 lakh",
    "Which diesel trucks can carry at least 2 tonnes?",
    "What commercial vehicles are available in Mumbai?",
)

CUMULATIVE_USAGE_FIELDS = (
    "llm_requests",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "audio_input_seconds",
    "tts_characters",
    "estimated_list_cost_inr",
)
