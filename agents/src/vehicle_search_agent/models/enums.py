from enum import StrEnum, auto


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
