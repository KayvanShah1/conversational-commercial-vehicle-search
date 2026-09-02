from __future__ import annotations

import asyncio
import re
from time import perf_counter
from typing import Any

from vehicle_search_utils import OperationLogContext, get_logger

from agents import Agent, RunConfig, RunContextWrapper, RunHooks, Runner, SQLiteSession
from vehicle_search_agent.agent import FallbackModel, build_agent
from vehicle_search_agent.models import AgentTurnResult, ConversationState, TurnMetrics, VoiceTurnResult
from vehicle_search_agent.response import conversational_response, natural_response
from vehicle_search_agent.settings import settings
from vehicle_search_agent.tools import AgentContext
from vehicle_search_agent.voice import synthesize_speech, transcribe_audio

logger = get_logger("VehicleSearchAgent")


def _tool_choice(transcript: str, state: ConversationState) -> str:
    """Force only explicit, non-reasoning references to prior vehicle facts."""
    if re.search(r"\b\d+(?:\.\d+)?\s*(?:lakhs?|lacs?|crores?)\b", transcript, re.IGNORECASE):
        return "search_vehicles"
    if not state.last_result_ids or re.search(
        r"\b(?:why|better|best|compare|suitable|recommend)\b", transcript, re.IGNORECASE
    ):
        return "auto"
    asks_for_facts = re.search(
        r"\b(?:details?|price|cost|year|kilometres?|mileage|fuel|payload|gvw|body|city|papers|condition|"
        r"uses?|category|size|axles?|carry|weight|brochures?|spec(?:ification)?s?|source|links?|"
        r"cheapest|lowest|highest)\b",
        transcript,
        re.IGNORECASE,
    )
    references_results = state.selected_listing_id is not None or re.search(
        r"\b(?:first|second|third|one|it|its|which|these|those|they|them|options?|vehicles?|results?|all three)\b",
        transcript,
        re.IGNORECASE,
    )
    return "get_vehicle_details" if asks_for_facts and references_results else "auto"


class AgentStageTimer(RunHooks[AgentContext]):
    async def on_llm_start(
        self,
        context: RunContextWrapper[AgentContext],
        agent: Agent[AgentContext],
        system_prompt: str | None,
        input_items: list[Any],
    ) -> None:
        del agent, system_prompt, input_items
        agent_context = context.context
        stage = "response" if agent_context.grounded_response else "understanding"
        agent_context.llm_operation = OperationLogContext(stage)

    async def on_llm_end(
        self, context: RunContextWrapper[AgentContext], agent: Agent[AgentContext], response: Any
    ) -> None:
        del agent, response
        agent_context = context.context
        operation = agent_context.llm_operation
        if operation is not None:
            completed = operation.completed_extra(status="succeeded")
            field = f"{operation.operation}_ms"
            elapsed = (getattr(agent_context, field) or 0) + completed["duration_ms"]
            setattr(agent_context, field, round(elapsed, 2))
            logger.info(f"{operation.operation}_completed", extra=completed)


class VehicleSearchSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.context = AgentContext(state=ConversationState(session_id=session_id))
        self.agent = build_agent()
        self.sdk_session = SQLiteSession(session_id, settings.session_db_path)
        self.hooks = AgentStageTimer()

    async def run_text_turn(self, transcript: str) -> AgentTurnResult:
        operation = OperationLogContext("agent_turn")
        self.context.reset_turn()
        self.context.current_input = transcript
        self.context.state.turn_number += 1
        if isinstance(self.agent.model, FallbackModel):
            self.agent.model.reset()
        self.agent.model_settings.tool_choice = _tool_choice(transcript, self.context.state)

        try:
            run_result = await Runner.run(
                self.agent,
                transcript,
                context=self.context,
                session=self.sdk_session,
                hooks=self.hooks,
                max_turns=settings.agent_runtime.max_turns,
                run_config=RunConfig(
                    workflow_name="vehicle_search_turn",
                    group_id=self.session_id,
                    trace_metadata={"turn_number": self.context.state.turn_number, "provider": "groq"},
                    tracing_disabled=not settings.agent_runtime.tracing_enabled,
                    trace_include_sensitive_data=settings.agent_runtime.trace_include_sensitive_data,
                ),
            )
        finally:
            self.agent.model_settings.tool_choice = "auto"

        grounded = self.context.grounded_response
        if grounded is None:
            spoken_response = conversational_response(
                run_result.final_output,
                first_turn=self.context.state.turn_number == 1,
                user_input=transcript,
            )
        else:
            spoken_response = natural_response(
                run_result.final_output,
                grounded,
                first_turn=self.context.state.turn_number == 1,
            )

        search_result = self.context.last_search_result
        completed = operation.completed_extra(status="succeeded")
        metrics = TurnMetrics(
            understanding_ms=self.context.understanding_ms,
            search_ms=search_result.search_ms if search_result else self.context.catalog_ms,
            response_ms=self.context.response_ms,
            total_ms=completed["duration_ms"],
        )
        completed.update(
            session_id=self.session_id,
            turn_number=self.context.state.turn_number,
            active_filters=self.context.state.active_filters.model_dump(exclude_none=True),
            result_ids=self.context.state.last_result_ids,
            timings_ms=metrics.model_dump(exclude_none=True),
        )
        logger.info("turn_completed", extra=completed)

        return AgentTurnResult(
            session_id=self.session_id,
            turn_number=self.context.state.turn_number,
            transcript=transcript,
            action=self.context.action,
            spoken_response=spoken_response,
            active_filters=self.context.state.active_filters,
            last_result_ids=self.context.state.last_result_ids,
            changed_fields=search_result.changed_fields if search_result else [],
            executed_filters=search_result.executed_filters if search_result else None,
            model_used=str(self.agent.model.model),
            metrics=metrics,
        )

    async def run_voice_turn(
        self, audio_bytes: bytes, *, filename: str = "recording.wav", speech_ended_at: float | None = None
    ) -> VoiceTurnResult:
        operation = OperationLogContext("voice_turn")
        speech_end = speech_ended_at if speech_ended_at is not None else perf_counter()

        transcription = await asyncio.to_thread(transcribe_audio, audio_bytes, filename=filename)
        turn = await self.run_text_turn(transcription.text)
        speech = await asyncio.to_thread(synthesize_speech, turn.spoken_response)
        audio_ready_at = perf_counter()

        completed = operation.completed_extra(status="succeeded", session_id=self.session_id)
        metrics = turn.metrics.model_copy(
            update={
                "stt_ms": transcription.duration_ms,
                "tts_ms": speech.duration_ms,
                "speech_end_to_audio_ready_ms": round((audio_ready_at - speech_end) * 1000, 2),
                "total_ms": completed["duration_ms"],
            }
        )
        logger.info("voice_turn_completed", extra={**completed, "timings_ms": metrics.model_dump(exclude_none=True)})

        return VoiceTurnResult(
            **turn.model_dump(exclude={"metrics"}),
            metrics=metrics,
            audio=speech.audio,
            audio_format=speech.format,
        )
