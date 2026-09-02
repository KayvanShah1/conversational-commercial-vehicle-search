from __future__ import annotations

import asyncio
import hashlib
from html import escape
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


def _hud() -> str:
    cells = "".join(
        f'<div class="hud-cell"><span>{escape(_metric_label(name))}</span><strong>{value:,.0f}</strong><small>ms</small></div>'
        for name, value in st.session_state.metrics.items()
    )
    return f'<div class="hud-grid">{cells}</div>'


def _slots() -> str:
    return "".join(
        f'<span class="slot"><small>{escape(SLOT_LABELS.get(name, name))}</small>{escape(_display_value(name, value))}</span>'
        for name, value in st.session_state.filters.items()
    )


_initialize_state()

st.markdown(
    """
    <style>
      .stApp { background: #f7f7f8; color: #202123; }
      [data-testid="stHeader"] { background: transparent; }
      .block-container { max-width: 1180px; padding-top: 1rem; padding-bottom: 1.5rem; }
      .vivi-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: .8rem; }
      .vivi-name { font-size: 1.75rem; font-weight: 750; letter-spacing: -.04em; }
      .vivi-name span { color: #5b5bd6; }
      .online { font-size: .7rem; letter-spacing: .08em; color: #247a55; }
      .online::before { content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #31a46c; margin-right: 6px; }
      .section-label { color: #6b6f7b; font-size: .72rem; font-weight: 700; letter-spacing: .08em; margin: .15rem 0 .55rem; text-transform: uppercase; }
      .st-key-chat_panel { background: #fff; border: 1px solid #e2e2e6 !important; border-radius: 14px; }
      .st-key-chat_panel [data-testid="stChatMessage"] { background: transparent; padding: .6rem .8rem; }
      [data-testid="stChatInput"] { border-color: #d9d9df; border-radius: 14px; }
      [data-testid="stAudioInput"] { background: #fff; border: 1px solid #e2e2e6; border-radius: 12px; padding: .55rem .75rem; }
      .slot-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 1rem; }
      .slot { background: #ececf4; border-radius: 8px; color: #30303b; font-size: .78rem; padding: 6px 8px; }
      .slot small { color: #777986; display: block; font-size: .56rem; letter-spacing: .05em; text-transform: uppercase; }
      .hud-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; margin-bottom: 1rem; }
      .hud-cell { background: #191a22; border: 1px solid #30313c; border-radius: 8px; color: #f5f5f7; padding: 7px 8px; }
      .hud-cell span { color: #9b9da9; display: block; font-size: .56rem; letter-spacing: .05em; overflow: hidden; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }
      .hud-cell strong { font-size: .9rem; font-variant-numeric: tabular-nums; }
      .hud-cell small { color: #858895; font-size: .58rem; margin-left: 2px; }
      .match-title { margin-bottom: 0 !important; }
      [data-testid="stExpander"] { background: #fff; border-color: #e2e2e6; }
      @media (max-width: 760px) {
        .block-container { padding-left: .8rem; padding-right: .8rem; }
        .hud-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="vivi-header"><div><div class="vivi-name"><span>V</span>ivi</div>'
    '<div style="color:#777986;font-size:.82rem">Commercial vehicle assistant</div></div>'
    '<div class="online">CATALOG ONLINE</div></div>',
    unsafe_allow_html=True,
)

chat_col, info_col = st.columns([3, 2], gap="large")

with chat_col:
    st.markdown('<div class="section-label">Conversation</div>', unsafe_allow_html=True)
    conversation = st.container(height=520, border=True, key="chat_panel")
    with conversation:
        if not st.session_state.messages:
            with st.chat_message("assistant"):
                st.write("Hi, I'm Vivi. What do you need to carry, and what budget are you working with?")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    prompt = st.chat_input("Message Vivi", key="text_message")
    recording = st.audio_input(
        "Or record in English or Hinglish",
        label_visibility="visible",
        key="voice_message",
    )
    if prompt:
        _run_text(prompt)
        st.rerun()
    if recording is not None:
        audio_bytes = recording.getvalue()
        fingerprint = hashlib.sha256(audio_bytes).hexdigest()
        if fingerprint != st.session_state.processed_audio:
            st.session_state.processed_audio = fingerprint
            _run_voice(audio_bytes, recording.name)
            st.rerun()
    if st.session_state.error:
        st.error(st.session_state.error)

with info_col:
    st.markdown('<div class="section-label">Current search</div>', unsafe_allow_html=True)
    if st.session_state.filters:
        st.markdown(f'<div class="slot-row">{_slots()}</div>', unsafe_allow_html=True)
    else:
        st.caption("Your budget, city, fuel and vehicle needs will appear here.")

    st.markdown('<div class="section-label">Top matches</div>', unsafe_allow_html=True)
    if st.session_state.vehicles:
        for row in st.session_state.vehicles:
            with st.container(border=True):
                st.markdown(f'**{row["Make / Model"]}** · {row["Year"]}', help=row["Why this match"])
                st.caption(
                    f'INR {row["Price (INR)"]:,.0f}  ·  {row["Fuel"]}  ·  '
                    f'{row["Payload (kg)"] or "—"} kg payload  ·  {row["City"]}'
                )
        with st.expander("All catalog fields"):
            st.dataframe(st.session_state.vehicles, hide_index=True, use_container_width=True)
    else:
        st.caption("Grounded catalog matches will appear after a search.")

    st.markdown('<div class="section-label">Performance</div>', unsafe_allow_html=True)
    if st.session_state.metrics:
        st.markdown(_hud(), unsafe_allow_html=True)
    else:
        st.caption("Per-stage timing appears after the first turn.")

    if st.session_state.reply_audio:
        st.audio(st.session_state.reply_audio, format=f"audio/{st.session_state.audio_format}", autoplay=True)
