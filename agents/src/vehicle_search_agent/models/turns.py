from pydantic import BaseModel, Field

from vehicle_search_agent.models.enums import AgentAction, SearchField
from vehicle_search_agent.models.filters import SearchFilters


class ConversationState(BaseModel):
    session_id: str
    active_filters: SearchFilters = Field(default_factory=SearchFilters)
    last_result_ids: list[str] = Field(default_factory=list, max_length=3)
    last_result_labels: list[str] = Field(default_factory=list, max_length=3)
    shown_result_ids: list[str] = Field(default_factory=list)
    selected_listing_id: str | None = None
    turn_number: int = Field(default=0, ge=0)


class TurnMetrics(BaseModel):
    stt_ms: float | None = None
    understanding_ms: float | None = None
    search_ms: float | None = None
    response_ms: float | None = None
    tts_ms: float | None = None
    speech_end_to_audio_ready_ms: float | None = None
    total_ms: float | None = None


class TurnUsage(BaseModel):
    llm_requests: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    audio_input_seconds: float | None = Field(default=None, ge=0)
    tts_characters: int | None = Field(default=None, ge=0)
    estimated_list_cost_usd: float | None = Field(default=None, ge=0)
    estimated_list_cost_inr: float | None = Field(default=None, ge=0)


class AgentTurnResult(BaseModel):
    session_id: str
    turn_number: int
    transcript: str
    action: AgentAction
    spoken_response: str
    active_filters: SearchFilters
    last_result_ids: list[str]
    changed_fields: list[SearchField]
    executed_filters: SearchFilters | None = None
    model_used: str
    metrics: TurnMetrics
    usage: TurnUsage


class VoiceTurnResult(AgentTurnResult):
    audio: bytes
    audio_format: str
