import asyncio
from time import perf_counter
from typing import Any
from unicodedata import normalize

from vehicle_search_utils import OperationLogContext, get_logger

from agents import Agent, ModelSettings, RunConfig, RunContextWrapper, RunHooks, Runner, SQLiteSession
from vehicle_search_agent.agent import FallbackModel, build_agent
from vehicle_search_agent.models import AgentTurnResult, ConversationState, TurnMetrics, TurnUsage, VoiceTurnResult
from vehicle_search_agent.pricing import USD_TO_INR, llm_list_cost_usd, voice_list_cost_usd
from vehicle_search_agent.response import conversational_response, natural_response
from vehicle_search_agent.settings import settings
from vehicle_search_agent.tools import AgentContext
from vehicle_search_agent.voice import synthesize_speech, transcribe_audio

logger = get_logger("VehicleSearchAgent")


def _match_text(value: str) -> str:
    """Normalize visually equivalent model text before grounding checks."""
    return " ".join(normalize("NFKC", value).casefold().split())


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
        agent_context = context.context
        usage = response.usage
        cost = llm_list_cost_usd(str(agent.model.model), usage.input_tokens, usage.output_tokens)
        if (usage.requests and not usage.total_tokens) or cost is None:
            agent_context.pricing_complete = False
        else:
            agent_context.llm_list_cost_usd += cost
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
            self.agent.model.start_turn()
        history_size = len(await self.sdk_session.get_items()) if self.context.state.last_result_labels else 0
        run_config = RunConfig(
            workflow_name="vehicle_search_turn",
            group_id=self.session_id,
            trace_metadata={"turn_number": self.context.state.turn_number, "provider": "groq"},
            tracing_disabled=not settings.agent_runtime.tracing_enabled,
            trace_include_sensitive_data=settings.agent_runtime.trace_include_sensitive_data,
        )
        run_result = await Runner.run(
            self.agent,
            transcript,
            context=self.context,
            session=self.sdk_session,
            hooks=self.hooks,
            max_turns=settings.agent_runtime.max_turns,
            run_config=run_config,
        )

        discarded_usage = None
        candidate = run_result.final_output if isinstance(run_result.final_output, str) else ""
        candidate_for_match = _match_text(candidate)
        named_catalog_answer = self.context.grounded_response is None and any(
            _match_text(label) in candidate_for_match for label in self.context.state.last_result_labels
        )
        if named_catalog_answer:
            logger.warning("ungrounded_catalog_answer_retried", extra={"tool": "get_vehicle_details"})
            discarded_usage = run_result.context_wrapper.usage
            new_item_count = len(await self.sdk_session.get_items()) - history_size
            for _ in range(new_item_count):
                await self.sdk_session.pop_item()
            run_config.model_settings = ModelSettings(tool_choice="get_vehicle_details")
            run_result = await Runner.run(
                self.agent,
                transcript,
                context=self.context,
                session=self.sdk_session,
                hooks=self.hooks,
                max_turns=settings.agent_runtime.max_turns,
                run_config=run_config,
            )

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
        sdk_usage = run_result.context_wrapper.usage
        if discarded_usage is not None:
            discarded_usage.add(sdk_usage)
            sdk_usage = discarded_usage
        estimated_cost_usd = self.context.llm_list_cost_usd if self.context.pricing_complete else None
        usage = TurnUsage(
            llm_requests=sdk_usage.requests,
            input_tokens=sdk_usage.input_tokens,
            cached_input_tokens=sdk_usage.input_tokens_details.cached_tokens,
            output_tokens=sdk_usage.output_tokens,
            reasoning_tokens=sdk_usage.output_tokens_details.reasoning_tokens,
            total_tokens=sdk_usage.total_tokens,
            estimated_list_cost_usd=estimated_cost_usd,
            estimated_list_cost_inr=estimated_cost_usd * USD_TO_INR if estimated_cost_usd is not None else None,
        )
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
            usage=usage.model_dump(exclude_none=True),
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
            model_used=(
                self.agent.model.route if isinstance(self.agent.model, FallbackModel) else str(self.agent.model.model)
            ),
            metrics=metrics,
            usage=usage,
        )

    async def run_voice_turn(
        self, audio_bytes: bytes, *, filename: str = "recording.wav", speech_ended_at: float
    ) -> VoiceTurnResult:
        operation = OperationLogContext("voice_turn")

        transcription = await asyncio.to_thread(transcribe_audio, audio_bytes, filename=filename)
        turn = await self.run_text_turn(transcription.text)
        speech = await asyncio.to_thread(synthesize_speech, turn.spoken_response)
        audio_ready_at = perf_counter()

        completed = operation.completed_extra(status="succeeded", session_id=self.session_id)
        metrics = turn.metrics.model_copy(
            update={
                "stt_ms": transcription.duration_ms,
                "tts_ms": speech.duration_ms,
                "speech_end_to_audio_ready_ms": round((audio_ready_at - speech_ended_at) * 1000, 2),
                "total_ms": completed["duration_ms"],
            }
        )
        voice_cost_usd = voice_list_cost_usd(
            transcription.audio_seconds,
            speech.character_count,
            stt_model=settings.groq.stt_model,
            tts_model=settings.groq.tts_model,
        )
        total_cost_usd = (
            turn.usage.estimated_list_cost_usd + voice_cost_usd
            if turn.usage.estimated_list_cost_usd is not None and voice_cost_usd is not None
            else None
        )
        usage = turn.usage.model_copy(
            update={
                "audio_input_seconds": transcription.audio_seconds,
                "tts_characters": speech.character_count,
                "estimated_list_cost_usd": total_cost_usd,
                "estimated_list_cost_inr": total_cost_usd * USD_TO_INR if total_cost_usd is not None else None,
            }
        )
        logger.info(
            "voice_turn_completed",
            extra={
                **completed,
                "timings_ms": metrics.model_dump(exclude_none=True),
                "usage": usage.model_dump(exclude_none=True),
            },
        )

        return VoiceTurnResult(
            **turn.model_dump(exclude={"metrics", "usage"}),
            metrics=metrics,
            usage=usage,
            audio=speech.audio,
            audio_format=speech.format,
        )
