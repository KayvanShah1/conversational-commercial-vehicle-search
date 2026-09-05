from enum import StrEnum, auto
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =============================================================================
# Agent operations and catalog vocabulary
# =============================================================================


class SearchField(StrEnum):
    budget_min = auto()
    budget_max = auto()
    city = auto()
    fuel = auto()
    body_type = auto()
    vehicle_category = auto()
    weight_class = auto()
    make = auto()
    model = auto()
    payload_min_kg = auto()
    gvw_min_kg = auto()
    papers_verified = auto()
    purpose = auto()


class CatalogTopic(StrEnum):
    cities = auto()
    vehicle_categories = auto()
    body_types = auto()
    fuels = auto()
    makes = auto()
    purposes = auto()


class AgentAction(StrEnum):
    conversation = auto()
    search = auto()
    details = auto()
    catalog_options = auto()


class VehicleCategory(StrEnum):
    mini_truck = auto()
    pickup = auto()
    rigid_truck = auto()


class WeightClass(StrEnum):
    light = auto()
    intermediate = auto()
    medium = auto()
    heavy = auto()


class BodyType(StrEnum):
    open = auto()
    flatbed = auto()
    box = auto()
    container = auto()
    tipper = auto()
    tanker = auto()
    reefer = auto()


class FuelType(StrEnum):
    cng = "CNG"
    diesel = "Diesel"


class PurposeTag(StrEnum):
    agriculture = auto()
    city_delivery = auto()
    cold_chain = auto()
    construction = auto()
    ecommerce = auto()
    fmcg = auto()
    fuel_transport = auto()
    heavy_delivery = auto()
    industrial_goods = auto()
    last_mile = auto()
    logistics = auto()
    long_haul = auto()
    market_transport = auto()
    mining = auto()
    parcel_delivery = auto()
    regional_delivery = auto()
    roadwork = auto()
    vegetable_delivery = auto()
    water_transport = auto()


class DetailField(StrEnum):
    year = auto()
    price = auto()
    km_driven = auto()
    fuel = auto()
    payload = auto()
    gvw = auto()
    body_type = auto()
    city = auto()
    papers_verified = auto()
    condition = auto()
    purpose_tags = auto()
    vehicle_category = auto()
    weight_class = auto()
    axle_count = auto()
    spec_source_url = auto()


# =============================================================================
# Search constraints and slot updates
# =============================================================================


class FilterValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_min: int | None = Field(default=None, ge=0, description="Minimum vehicle price in INR")
    budget_max: int | None = Field(default=None, ge=0, description="Maximum vehicle price in INR")
    city: str | None = Field(
        default=None,
        description="Vehicle listing or pickup city; for a route, use its origin city",
    )
    fuel: FuelType | None = None
    body_type: BodyType | None = Field(
        default=None,
        description="Physical cargo body explicitly requested by the user; do not infer it from the cargo or purpose",
    )
    vehicle_category: VehicleCategory | None = Field(
        default=None,
        description="Catalog construction class: mini_truck, pickup, or rigid_truck",
    )
    weight_class: WeightClass | None = Field(
        default=None,
        description="Vehicle size or capacity class: light, intermediate, medium, or heavy",
    )
    make: str | None = None
    model: str | None = None
    payload_min_kg: int | None = Field(default=None, ge=0)
    gvw_min_kg: int | None = Field(default=None, ge=0)
    papers_verified: bool | None = None
    purpose: PurposeTag | None = Field(
        default=None,
        description="Best-fit intended work or route type inferred from the user's need; used only for ranking",
    )

    @field_validator("city", "make", "model", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("fuel", mode="before")
    @classmethod
    def normalize_fuel(cls, value: str | FuelType | None) -> str | FuelType | None:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        return {"cng": "CNG", "diesel": "Diesel"}.get(cleaned.casefold(), cleaned or None)


class SearchFilters(FilterValues):
    @model_validator(mode="after")
    def validate_budget(self) -> Self:
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budget_min cannot exceed budget_max")
        return self


class SlotPatch(FilterValues):
    """Only constraints added, corrected, or removed in the current turn."""

    clear_fields: list[SearchField] = Field(default_factory=list)


def merge_slot_patch(current: SearchFilters, patch: SlotPatch) -> tuple[SearchFilters, list[SearchField]]:
    values = current.model_dump()
    values.update(dict.fromkeys(field.value for field in patch.clear_fields))
    values.update(patch.model_dump(exclude={"clear_fields"}, exclude_none=True))
    updated = SearchFilters(**values)
    changed = [
        SearchField(field) for field in SearchFilters.model_fields if getattr(current, field) != getattr(updated, field)
    ]
    return updated, changed


# =============================================================================
# Persisted conversation state
# =============================================================================


class ConversationState(BaseModel):
    session_id: str
    active_filters: SearchFilters = Field(default_factory=SearchFilters)
    last_result_ids: list[str] = Field(default_factory=list, max_length=3)
    last_result_labels: list[str] = Field(default_factory=list, max_length=3)
    shown_result_ids: list[str] = Field(default_factory=list)
    selected_listing_id: str | None = None
    turn_number: int = Field(default=0, ge=0)


# =============================================================================
# Catalog records, ranking, and search results
# =============================================================================


class VehicleRecord(BaseModel):
    listing_id: str
    make: str
    model: str
    year: int
    price_inr: int = Field(gt=0)
    km_driven: int = Field(ge=0)
    fuel: str
    payload_kg: int | None = Field(default=None, gt=0)
    payload_is_estimated: bool = False
    gvw_kg: int = Field(gt=0)
    vehicle_category: str
    weight_class: str
    body_type: str
    axle_count: int = Field(ge=2)
    city: str
    papers_verified: bool
    condition: str
    purpose_tags: list[str]
    spec_source_url: str


class RankingBreakdown(BaseModel):
    purpose: float = Field(ge=0)
    papers_verified: float = Field(ge=0)
    budget: float = Field(ge=0)
    mileage: float = Field(ge=0)
    condition: float = Field(ge=0)
    year: float = Field(ge=0)
    total: float = Field(ge=0)


class RankedVehicle(BaseModel):
    vehicle: VehicleRecord
    score: RankingBreakdown


class VehicleSearchResult(BaseModel):
    executed_filters: SearchFilters
    changed_fields: list[SearchField]
    vehicles: list[RankedVehicle] = Field(max_length=3)
    total_matches: int = Field(ge=0)
    relaxation: str | None = None
    search_ms: float = Field(ge=0)


# =============================================================================
# Per-turn observability and public results
# =============================================================================


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
