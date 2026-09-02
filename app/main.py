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
    try:
        with st.spinner("Vivi is checking the catalog..."):
            session = _session()
            result = asyncio.run(session.run_text_turn(message))
        _save_result(result, session)
    except Exception as error:  # noqa: BLE001 - keep the live demo usable after a provider failure
        st.session_state.error = f"Text turn failed: {type(error).__name__}. Check the terminal logs and retry."


def _run_voice(audio_bytes: bytes, filename: str) -> None:
    try:
        with st.spinner("Vivi is listening and checking the catalog..."):
            session = _session()
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
        "total_ms": "Total",
        "speech_end_to_audio_ready_ms": "Speech to audio",
    }.get(name, name.replace("_ms", "").replace("_", " ").title())


def _reset_conversation() -> None:
    st.session_state.clear()
    st.rerun()


def _render_sidebar() -> None:
    with st.sidebar:
        st.title("Vivi")
        st.caption("Commercial vehicle assistant")
        st.badge("Catalog connected", icon=":material/database:", color="green")
        st.button(
            "New conversation",
            icon=":material/add:",
            width="stretch",
            on_click=_reset_conversation,
        )

        st.divider()
        st.subheader("Current search")
        if st.session_state.filters:
            with st.container(horizontal=True, wrap=True):
                for name, value in st.session_state.filters.items():
                    label = SLOT_LABELS.get(name, name.replace("_", " ").title())
                    st.badge(f"{label}: {_display_value(name, value)}", color="gray")
        else:
            st.caption("Budget, location and vehicle needs will stay visible here.")

        st.divider()
        st.subheader("Turn timing")
        if st.session_state.metrics:
            with st.container(horizontal=True, wrap=True):
                for name, value in st.session_state.metrics.items():
                    st.badge(f"{_metric_label(name)} {value:,.0f} ms", color="gray")
        else:
            st.caption("Stage timings appear after the first turn.")


def _render_matches() -> None:
    if not st.session_state.vehicles:
        return

    st.subheader("Current top matches")
    columns = st.columns(len(st.session_state.vehicles), gap="medium")
    for column, vehicle in zip(columns, st.session_state.vehicles, strict=True):
        with column, st.container(border=True):
            st.markdown(f'#### {vehicle["Make / Model"]}')
            st.caption(f'{vehicle["Year"]} · {vehicle["City"]} · {vehicle["Body"].title()} body')
            st.metric("Price", f'₹{vehicle["Price (INR)"]:,.0f}')
            st.write(f'**Fuel:** {vehicle["Fuel"]}')
            st.write(f'**Payload:** {vehicle["Payload (kg)"] or "—"} kg')
            st.write(f'**GVW:** {vehicle["GVW (kg)"] or "—"} kg')
            st.caption(f'{vehicle["Papers"]} · Match: {vehicle["Why this match"]}')

    with st.expander("Compare every catalog field"):
        st.dataframe(
            st.session_state.vehicles,
            hide_index=True,
            width="stretch",
            column_config={
                "Price (INR)": st.column_config.NumberColumn(format="₹%d"),
                "KM": st.column_config.NumberColumn(format="%d km"),
                "Payload (kg)": st.column_config.NumberColumn(format="%d kg"),
                "GVW (kg)": st.column_config.NumberColumn(format="%d kg"),
            },
        )


def _handle_submission(submission) -> None:
    if isinstance(submission, str):
        if submission.strip():
            _run_text(submission.strip())
        return

    if submission.audio is not None:
        audio_bytes = submission.audio.getvalue()
        fingerprint = hashlib.sha256(audio_bytes).hexdigest()
        if fingerprint != st.session_state.processed_audio:
            st.session_state.processed_audio = fingerprint
            _run_voice(audio_bytes, submission.audio.name)
    elif submission.text.strip():
        _run_text(submission.text.strip())


_initialize_state()

st.markdown(
    """
    <style>
      .block-container {
        max-width: none;
        padding: 1.25rem 2.25rem 7rem;
      }
      [data-testid="stHeader"] { background: transparent; }
      [data-testid="stChatMessage"] { padding-block: 1rem; }
      @media (max-width: 760px) {
        .block-container { padding: .75rem .9rem 6rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

_render_sidebar()

header, status = st.columns([5, 1], vertical_alignment="center")
with header:
    st.title("Find the right commercial vehicle")
    st.caption("Chat naturally in English or Hinglish. Your results are grounded in the catalog.")
with status:
    st.badge("Voice + text ready", icon=":material/mic:", color="violet")

if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write(
            "Hi, I'm Vivi. Tell me what you need to carry, where you operate, "
            "and your budget—I’ll help you find suitable commercial vehicles."
        )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if st.session_state.reply_audio:
    with st.chat_message("assistant"):
        st.audio(st.session_state.reply_audio, format=f"audio/{st.session_state.audio_format}")

_render_matches()

if st.session_state.error:
    st.error(st.session_state.error)

submission = st.chat_input(
    "Describe a vehicle need or ask a follow-up",
    accept_audio=True,
    audio_sample_rate=16_000,
    key="message",
)
if submission:
    _handle_submission(submission)
    st.rerun()
