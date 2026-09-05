from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vehicle_search_agent.models.enums import (
    BodyType,
    FuelType,
    PurposeTag,
    SearchField,
    VehicleCategory,
    WeightClass,
)


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
