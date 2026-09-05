import asyncio
import hashlib
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import streamlit as st
from components import display_response, render_matches, render_sidebar, render_starter_questions
from config import CUMULATIVE_USAGE_FIELDS, TOOL_NAMES
from vehicle_search_agent.models import AgentTurnResult
from vehicle_search_agent.runner import VehicleSearchSession

st.set_page_config(page_title="Vivi vehicle search", page_icon="🚚", layout="wide")


def _initialize_state() -> None:
    defaults = {
        "session_id": f"web-{uuid4().hex}",
        "vehicle_session": None,
        "last_search_result": None,
        "messages": [],
        "metrics": {},
        "usage": {},
        "conversation_totals": {
            "turns": 0,
            "total_ms": 0.0,
            **dict.fromkeys(CUMULATIVE_USAGE_FIELDS, 0),
        },
        "last_tool": None,
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


def _save_result(result: AgentTurnResult, session: VehicleSearchSession) -> None:
    st.session_state.messages.append({"role": "assistant", "content": display_response(result, session)})
    if session.context.last_search_result is not None:
        st.session_state.last_search_result = session.context.last_search_result
    st.session_state.metrics = result.metrics.model_dump(mode="json", exclude_none=True)
    st.session_state.usage = result.usage.model_dump(mode="json", exclude_none=True)
    _update_conversation_totals(result)
    st.session_state.last_tool = TOOL_NAMES[result.action.value]
    st.session_state.error = None


def _update_conversation_totals(result: AgentTurnResult) -> None:
    totals = st.session_state.conversation_totals
    totals["turns"] += 1
    totals["total_ms"] += result.metrics.total_ms or 0
    for field in CUMULATIVE_USAGE_FIELDS:
        totals[field] += getattr(result.usage, field) or 0


def _run_text(message: str) -> None:
    st.session_state.messages.append({"role": "user", "content": message})
    st.session_state.reply_audio = None
    try:
        with st.spinner("Vivi is thinking..."):
            session = _session()
            result = asyncio.run(session.run_text_turn(message))
        _save_result(result, session)
    except Exception as error:  # noqa: BLE001 - keep the live demo usable after a provider failure
        st.session_state.error = f"Text turn failed: {type(error).__name__}. Check the terminal logs and retry."


def _run_voice(audio_bytes: bytes, filename: str, speech_ended_at: float) -> None:
    st.session_state.reply_audio = None
    try:
        with st.spinner("Vivi is listening..."):
            session = _session()
            result = asyncio.run(
                session.run_voice_turn(audio_bytes, filename=filename, speech_ended_at=speech_ended_at)
            )
        st.session_state.messages.append({"role": "user", "content": result.transcript})
        _save_result(result, session)
        st.session_state.reply_audio = result.audio
        st.session_state.audio_format = result.audio_format
    except Exception as error:  # noqa: BLE001 - keep the live demo usable after a provider failure
        st.session_state.error = f"Voice turn failed: {type(error).__name__}. Check the terminal logs and retry."


def _reset_conversation() -> None:
    st.session_state.clear()
    st.rerun()


def _handle_submission(submission) -> None:
    if isinstance(submission, str):
        if submission.strip():
            _run_text(submission.strip())
        return

    if submission.audio is not None:
        submitted_at = perf_counter()
        audio_bytes = submission.audio.getvalue()
        fingerprint = hashlib.sha256(audio_bytes).hexdigest()
        if fingerprint != st.session_state.processed_audio:
            st.session_state.processed_audio = fingerprint
            _run_voice(audio_bytes, submission.audio.name, submitted_at)
    elif submission.text.strip():
        _run_text(submission.text.strip())


_initialize_state()

styles = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)

render_sidebar(_reset_conversation)

with st.container(key="page_header"):
    st.title("Find the right commercial vehicle")
    st.caption("Natural English or Hinglish, grounded in the vehicle catalog.")

with st.container(key="status_rail", horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
    st.badge("Voice + text", icon=":material/mic:", color="primary")
    if st.session_state.last_tool:
        st.badge(
            st.session_state.last_tool,
            icon=(":material/check_circle:" if st.session_state.last_tool == "No tool" else ":material/build:"),
            color="gray",
            help="Tool used on the latest turn",
        )

with st.chat_message("assistant"):
    st.write(
        "Hi, I'm Vivi. Tell me what you need to carry, where you operate, "
        "and your budget. I'll help you find suitable commercial vehicles."
    )

render_starter_questions(_run_text)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.markdown(message["content"])
        else:
            st.write(message["content"])

if st.session_state.reply_audio:
    with st.chat_message("assistant"):
        st.audio(st.session_state.reply_audio, format=f"audio/{st.session_state.audio_format}")

render_matches(st.session_state.last_search_result)

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
