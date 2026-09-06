from pydantic import BaseModel, Field

from vehicle_search_agent.models.enums import SearchField
from vehicle_search_agent.models.filters import SearchFilters


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
    km_driven: float = Field(ge=0)
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
