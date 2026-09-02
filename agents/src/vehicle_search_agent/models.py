from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SearchField(StrEnum):
    budget_min = "budget_min"
    budget_max = "budget_max"
    city = "city"
    fuel = "fuel"
    body_type = "body_type"
    vehicle_category = "vehicle_category"
    weight_class = "weight_class"
    make = "make"
    model = "model"
    payload_min_kg = "payload_min_kg"
    gvw_min_kg = "gvw_min_kg"
    papers_verified = "papers_verified"
    purpose = "purpose"


class CatalogTopic(StrEnum):
    cities = "cities"
    vehicle_categories = "vehicle_categories"
    body_types = "body_types"
    fuels = "fuels"
    makes = "makes"


class AgentAction(StrEnum):
    conversation = "conversation"
    search = "search"
    details = "details"
    catalog_options = "catalog_options"


class VehicleCategory(StrEnum):
    mini_truck = "mini_truck"
    pickup = "pickup"
    rigid_truck = "rigid_truck"


class WeightClass(StrEnum):
    light = "light"
    intermediate = "intermediate"
    medium = "medium"
    heavy = "heavy"


class FilterValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_min: int | None = Field(default=None, ge=0, description="Minimum vehicle price in INR")
    budget_max: int | None = Field(default=None, ge=0, description="Maximum vehicle price in INR")
    city: str | None = Field(
        default=None,
        description="Vehicle listing or pickup city; for a route, use its origin city",
    )
    fuel: str | None = None
    body_type: str | None = Field(
        default=None,
        description="Physical cargo body explicitly requested by the user; do not infer it from the cargo or purpose",
    )
    vehicle_category: VehicleCategory | None = Field(
        default=None,
        description="Catalog construction class: mini_truck, pickup, or rigid_truck",
    )
    weight_class: WeightClass | None = Field(
        default=None,
        description="Vehicle size or capacity class: light, medium, or heavy",
    )
    make: str | None = None
    model: str | None = None
    payload_min_kg: int | None = Field(default=None, ge=0)
    gvw_min_kg: int | None = Field(default=None, ge=0)
    papers_verified: bool | None = None
    purpose: str | None = Field(
        default=None,
        description="Best-fit intended work or route type inferred from the user's need; used only for ranking",
    )

    @field_validator("city", "fuel", "make", "model", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("fuel", mode="after")
    @classmethod
    def normalize_fuel(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return {"cng": "CNG", "diesel": "Diesel"}.get(value.casefold(), value)

class SearchFilters(FilterValues):
    @model_validator(mode="after")
    def validate_budget(self) -> SearchFilters:
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


class ConversationState(BaseModel):
    session_id: str
    active_filters: SearchFilters = Field(default_factory=SearchFilters)
    last_result_ids: list[str] = Field(default_factory=list, max_length=3)
    shown_result_ids: list[str] = Field(default_factory=list)
    selected_listing_id: str | None = None
    turn_number: int = Field(default=0, ge=0)


class VehicleRecord(BaseModel):
    listing_id: str
    make: str
    model: str
    year: int
    price_inr: int = Field(gt=0)
    km_driven: int = Field(ge=0)
    fuel: str
    payload_kg: int | None = Field(default=None, gt=0)
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


class DetailField(StrEnum):
    year = "year"
    price = "price"
    km_driven = "km_driven"
    fuel = "fuel"
    payload = "payload"
    gvw = "gvw"
    body_type = "body_type"
    city = "city"
    papers_verified = "papers_verified"
    condition = "condition"
    purpose_tags = "purpose_tags"
    vehicle_category = "vehicle_category"
    weight_class = "weight_class"
    axle_count = "axle_count"
    spec_source_url = "spec_source_url"


class TurnMetrics(BaseModel):
    stt_ms: float | None = None
    understanding_ms: float | None = None
    search_ms: float | None = None
    response_ms: float | None = None
    tts_ms: float | None = None
    speech_end_to_audio_ready_ms: float | None = None
    total_ms: float | None = None


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


class VoiceTurnResult(AgentTurnResult):
    audio: bytes
    audio_format: str
