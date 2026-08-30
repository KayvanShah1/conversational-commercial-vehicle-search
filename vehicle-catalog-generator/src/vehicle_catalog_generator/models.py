from enum import StrEnum, auto

from pydantic import BaseModel, Field


class VehicleCondition(StrEnum):
    excellent = auto()
    good = auto()
    fair = auto()


class VehicleCategory(StrEnum):
    mini_truck = auto()
    pickup = auto()
    rigid_truck = auto()


class VehicleWeightClass(StrEnum):
    light = auto()
    intermediate = auto()
    medium = auto()
    heavy = auto()


class VehicleBodyType(StrEnum):
    open = auto()
    flatbed = auto()
    box = auto()
    container = auto()
    tipper = auto()
    tanker = auto()
    reefer = auto()


class VehicleReference(BaseModel):
    make: str
    model: str
    fuel: str
    vehicle_category: VehicleCategory
    weight_class: VehicleWeightClass
    body_type: VehicleBodyType
    axle_count: int = Field(ge=2)
    payload_kg: int | None = Field(default=None, gt=0)
    gvw_kg: int = Field(gt=0)
    new_vehicle_price_anchor_inr: int = Field(gt=0)
    purpose_tags: list[str]
    spec_source_url: str
    payload_is_estimated: bool = False


class VehicleListing(BaseModel):
    listing_id: str
    make: str
    model: str
    year: int
    price_inr: int = Field(gt=0)
    km_driven: int = Field(ge=0)
    fuel: str
    payload_kg: int | None = Field(default=None, gt=0)
    gvw_kg: int = Field(gt=0)
    vehicle_category: VehicleCategory
    weight_class: VehicleWeightClass
    body_type: VehicleBodyType
    axle_count: int = Field(ge=2)
    city: str
    papers_verified: bool
    condition: VehicleCondition
    purpose_tags: list[str]
