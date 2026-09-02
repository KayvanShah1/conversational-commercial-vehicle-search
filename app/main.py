from __future__ import annotations

import asyncio
import hashlib
from uuid import uuid4

import streamlit as st
from vehicle_search_agent.models import RankedVehicle
from vehicle_search_agent.runner import VehicleSearchSession

st.set_page_config(page_title="Vivi vehicle search", page_icon="🚚", layout="wide")

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


def _initialize_state() -> None:
    defaults = {
        "session_id": f"web-{uuid4().hex}",
        "vehicle_session": None,
        "messages": [],
        "filters": {},
        "vehicles": [],
        "metrics": {},
        "reply_audio": None,
        "audio_format": "wav",
        "processed_audio": None,
        "error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _session() -> VehicleSearchSession:
    if st.session_state.vehicle_session is None:
        st.session_state.vehicle_session = VehicleSearchSession(st.session_state.session_id)
    return st.session_state.vehicle_session


def _reason(ranked: RankedVehicle, purpose: str | None) -> str:
    if purpose and ranked.score.purpose > 0:
        return purpose.replace("_", " ")
    if ranked.vehicle.papers_verified:
        return "Verified papers"
    return f"{ranked.vehicle.condition.title()} condition"


def _vehicle_rows(session: VehicleSearchSession) -> list[dict]:
    result = session.context.last_search_result
    if result is None:
        return []
    return [
        {
            "Make / Model": f"{ranked.vehicle.make} {ranked.vehicle.model}",
            "Year": ranked.vehicle.year,
            "Price (INR)": ranked.vehicle.price_inr,
            "KM": ranked.vehicle.km_driven,
            "Fuel": ranked.vehicle.fuel,
            "Payload (kg)": ranked.vehicle.payload_kg,
            "GVW (kg)": ranked.vehicle.gvw_kg,
            "Body": ranked.vehicle.body_type,
            "City": ranked.vehicle.city,
            "Papers": "Verified" if ranked.vehicle.papers_verified else "Not verified",
            "Why this match": _reason(ranked, result.executed_filters.purpose),
        }
        for ranked in result.vehicles
    ]


def _save_result(result, session: VehicleSearchSession) -> None:
    st.session_state.messages.extend(
        [
            {"role": "user", "content": result.transcript},
            {"role": "assistant", "content": result.spoken_response},
        ]
    )
    st.session_state.filters = result.active_filters.model_dump(mode="json", exclude_none=True)
    new_vehicles = _vehicle_rows(session)
    if new_vehicles:
        st.session_state.vehicles = new_vehicles
    st.session_state.metrics = result.metrics.model_dump(mode="json", exclude_none=True)
    st.session_state.error = None


def _run_text(message: str) -> None:
    session = _session()
    try:
        with st.spinner("Vivi is checking the catalog..."):
            result = asyncio.run(session.run_text_turn(message))
        _save_result(result, session)
    except Exception as error:  # noqa: BLE001 - keep the live demo usable after a provider failure
        st.session_state.error = f"Text turn failed: {type(error).__name__}. Check the terminal logs and retry."


def _run_voice(audio_bytes: bytes, filename: str) -> None:
    session = _session()
    try:
        with st.spinner("Transcribing, searching, and preparing Vivi's reply..."):
            result = asyncio.run(session.run_voice_turn(audio_bytes, filename=filename))
        _save_result(result, session)
        st.session_state.reply_audio = result.audio
        st.session_state.audio_format = result.audio_format
    except Exception as error:  # noqa: BLE001 - keep the live demo usable after a provider failure
        st.session_state.error = f"Voice turn failed: {type(error).__name__}. Check the terminal logs and retry."


def _display_value(name: str, value) -> str:
    if name in {"budget_min", "budget_max"}:
        return f"₹{value:,.0f}"
    if name in {"payload_min_kg", "gvw_min_kg"}:
        return f"{value:,.0f} kg"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value).replace("_", " ").title()


def _metric_label(name: str) -> str:
    return {
        "stt_ms": "STT",
        "understanding_ms": "Understanding",
        "search_ms": "Search",
        "response_ms": "Response",
        "tts_ms": "TTS",
        "total_ms": "Total turn",
        "speech_end_to_audio_ready_ms": "Speech end to first audio available",
    }.get(name, name.replace("_ms", "").replace("_", " ").title())


_initialize_state()

st.markdown(
    """
    <style>
      .stApp { background: #f5f6f9; color: #171925; }
      [data-testid="stHeader"] { background: transparent; }
      .block-container { max-width: 1440px; padding-top: 1.5rem; }
      h1 { color: #2929a8; letter-spacing: -0.04em; margin-bottom: 0; }
      [data-testid="stAudioInput"] { border: 1px solid #dfe2ea; border-radius: 12px; padding: 1rem; background: white; }
      [data-testid="stChatMessage"], [data-testid="stDataFrame"], [data-testid="stMetric"] {
        border: 1px solid #dfe2ea; border-radius: 10px; background: white;
      }
      [data-testid="stMetric"] { padding: .75rem 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

title_col, status_col = st.columns([4, 1])
with title_col:
    st.title("Vivi")
    st.caption("Find the right commercial vehicle")
with status_col:
    st.success("Catalog ready")

main_col, side_col = st.columns([2.2, 1], gap="large")

with main_col:
    st.subheader("Hold to talk")
    recording = st.audio_input("Record your requirement in English or Hinglish")
    if recording is not None:
        audio_bytes = recording.getvalue()
        fingerprint = hashlib.sha256(audio_bytes).hexdigest()
        if fingerprint != st.session_state.processed_audio:
            st.session_state.processed_audio = fingerprint
            _run_voice(audio_bytes, recording.name)
            st.rerun()

    prompt = st.chat_input("Type your requirement or a follow-up question")
    if prompt:
        _run_text(prompt)
        st.rerun()

    if st.session_state.error:
        st.error(st.session_state.error)

    conversation = st.container(height=260, border=True)
    with conversation:
        if not st.session_state.messages:
            st.caption("Start with a requirement, ask what is available, or simply say hi.")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    st.subheader("Top matches")
    if st.session_state.vehicles:
        st.dataframe(st.session_state.vehicles, hide_index=True, use_container_width=True)
    else:
        st.info("Grounded catalog results will appear here after a search.")

    st.subheader("Play response")
    if st.session_state.reply_audio:
        st.audio(st.session_state.reply_audio, format=f"audio/{st.session_state.audio_format}", autoplay=True)
    else:
        st.caption("A spoken reply appears here after a voice turn.")

with side_col:
    st.subheader("Current understanding")
    if st.session_state.filters:
        for name, value in st.session_state.filters.items():
            st.metric(SLOT_LABELS.get(name, name.replace("_", " ").title()), _display_value(name, value))
    else:
        st.caption("Waiting for a requirement. Slots remain visible here on every turn.")

    st.subheader("Latency")
    if st.session_state.metrics:
        for name, value in st.session_state.metrics.items():
            st.metric(_metric_label(name), f"{value:,.0f} ms")
    else:
        st.caption("Stage timings appear after the first turn.")
