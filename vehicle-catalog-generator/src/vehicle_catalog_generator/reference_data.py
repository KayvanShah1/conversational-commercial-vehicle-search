from dataclasses import dataclass

from vehicle_catalog_generator.models import (
    VehicleBodyType,
    VehicleCategory,
    VehicleCondition,
    VehicleReference,
    VehicleWeightClass,
)


@dataclass(frozen=True)
class GenerationParameters:
    new_vehicle_km_range: tuple[int, int] = (1_000, 12_000)
    km_variance_range: tuple[float, float] = (0.75, 1.25)
    minimum_km_driven: int = 1_000
    annual_depreciation_rate: float = 0.10
    minimum_age_factor: float = 0.30
    mileage_depreciation_distance_km: int = 500_000
    minimum_mileage_factor: float = 0.75
    market_noise_range: tuple[float, float] = (0.92, 1.08)
    minimum_price_inr: int = 150_000
    price_rounding_interval_inr: int = 5_000


GENERATION_PARAMETERS = GenerationParameters()

CONDITION_WEIGHTS: dict[VehicleCondition, float] = {
    VehicleCondition.excellent: 0.20,
    VehicleCondition.good: 0.55,
    VehicleCondition.fair: 0.25,
}

CONDITION_PRICE_FACTORS: dict[VehicleCondition, float] = {
    VehicleCondition.excellent: 1.05,
    VehicleCondition.good: 1.00,
    VehicleCondition.fair: 0.88,
}

# Demo-oriented weights that keep every searchable class well represented.
# These are synthetic catalog assumptions, not estimates of the real vehicle market.
WEIGHT_CLASS_WEIGHTS: dict[VehicleWeightClass, float] = {
    VehicleWeightClass.light: 0.45,
    VehicleWeightClass.intermediate: 0.15,
    VehicleWeightClass.medium: 0.15,
    VehicleWeightClass.heavy: 0.25,
}

CITY_WEIGHTS = {
    "Mumbai": 0.14,
    "Delhi": 0.13,
    "Pune": 0.10,
    "Bengaluru": 0.10,
    "Ahmedabad": 0.09,
    "Hyderabad": 0.09,
    "Chennai": 0.08,
    "Kolkata": 0.07,
    "Surat": 0.06,
    "Jaipur": 0.05,
    "Nagpur": 0.04,
    "Indore": 0.05,
}

VEHICLE_REFERENCES = [
    VehicleReference(
        make="Tata",
        model="Ace Gold",
        fuel="CNG",
        vehicle_category=VehicleCategory.mini_truck,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.box,
        axle_count=2,
        payload_kg=660,
        gvw_kg=1630,
        new_vehicle_price_anchor_inr=650_000,
        purpose_tags=["city_delivery", "last_mile", "fmcg", "vegetable_delivery"],
        spec_source_url=("https://smalltrucks.tatamotors.com/assets/smalltrucks/files/2025-01/ACE%20GOLD%20CNG.pdf"),
    ),
    VehicleReference(
        make="Tata",
        model="Ace Gold",
        fuel="Diesel",
        vehicle_category=VehicleCategory.mini_truck,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.open,
        axle_count=2,
        payload_kg=900,
        gvw_kg=1835,
        new_vehicle_price_anchor_inr=700_000,
        purpose_tags=["city_delivery", "logistics", "construction"],
        spec_source_url="https://smalltrucks.tatamotors.com/tata-ace-gold-diesel",
    ),
    VehicleReference(
        make="Tata",
        model="Intra V10",
        fuel="Diesel",
        vehicle_category=VehicleCategory.mini_truck,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.flatbed,
        axle_count=2,
        payload_kg=1000,
        gvw_kg=2120,
        new_vehicle_price_anchor_inr=750_000,
        purpose_tags=["city_delivery", "market_transport", "logistics"],
        spec_source_url="https://smalltrucks.tatamotors.com/tata-intra-v10",
    ),
    VehicleReference(
        make="Tata",
        model="Intra V30 Gold",
        fuel="Diesel",
        vehicle_category=VehicleCategory.pickup,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.open,
        axle_count=2,
        payload_kg=1500,
        gvw_kg=2775,
        new_vehicle_price_anchor_inr=850_000,
        purpose_tags=["regional_delivery", "construction", "logistics"],
        spec_source_url="https://smalltrucks.tatamotors.com/tata-intra-v30-gold",
    ),
    VehicleReference(
        make="Tata",
        model="Intra V50",
        fuel="Diesel",
        vehicle_category=VehicleCategory.pickup,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.flatbed,
        axle_count=2,
        payload_kg=1500,
        gvw_kg=2940,
        new_vehicle_price_anchor_inr=925_000,
        purpose_tags=["regional_delivery", "construction", "industrial_goods"],
        spec_source_url=(
            "https://smalltrucks.tatamotors.com/sites/default/files/product/brochure/"
            "Intra_V50%20Brochure%20Low%20res.pdf"
        ),
    ),
    VehicleReference(
        make="Mahindra",
        model="Jeeto Strong Diesel",
        fuel="Diesel",
        vehicle_category=VehicleCategory.mini_truck,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.box,
        axle_count=2,
        payload_kg=815,
        gvw_kg=1605,
        new_vehicle_price_anchor_inr=525_000,
        purpose_tags=["city_delivery", "last_mile", "vegetable_delivery"],
        spec_source_url="https://mahindralastmilemobility.com/jeeto-strong-diesel-cargo",
    ),
    VehicleReference(
        make="Mahindra",
        model="Bolero Pik-Up",
        fuel="Diesel",
        vehicle_category=VehicleCategory.pickup,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.open,
        axle_count=2,
        payload_kg=1700,
        gvw_kg=3490,
        new_vehicle_price_anchor_inr=950_000,
        purpose_tags=["regional_delivery", "agriculture", "construction"],
        spec_source_url=(
            "https://auto.mahindra.com/on/demandware.static/-/Sites-amc-Library/en_IN/"
            "-/media/project/mahindra/dotcom/mahindra/in-news---home/pr/brochure/1st.pdf"
        ),
    ),
    VehicleReference(
        make="Ashok Leyland",
        model="Dost XL",
        fuel="Diesel",
        vehicle_category=VehicleCategory.mini_truck,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.flatbed,
        axle_count=2,
        payload_kg=1400,
        gvw_kg=2625,
        new_vehicle_price_anchor_inr=850_000,
        purpose_tags=["city_delivery", "regional_delivery", "logistics"],
        spec_source_url=(
            "https://www.ashokleyland.com/in/lightvehicles/smallcommercialvechicles/dost-xl/specification"
        ),
    ),
    VehicleReference(
        make="Ashok Leyland",
        model="Bada Dost",
        fuel="CNG",
        vehicle_category=VehicleCategory.mini_truck,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.reefer,
        axle_count=2,
        payload_kg=1246,
        gvw_kg=2880,
        new_vehicle_price_anchor_inr=900_000,
        purpose_tags=["city_delivery", "fmcg", "regional_delivery"],
        spec_source_url=(
            "https://www.ashokleyland.com/in/lightvehicles/smallcommercialvechicles/bada-dost-cng/specification"
        ),
    ),
    VehicleReference(
        make="Ashok Leyland",
        model="Bada Dost i4",
        fuel="Diesel",
        vehicle_category=VehicleCategory.pickup,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.container,
        axle_count=2,
        payload_kg=1825,
        gvw_kg=3490,
        new_vehicle_price_anchor_inr=1_000_000,
        purpose_tags=["regional_delivery", "construction", "logistics"],
        spec_source_url=(
            "https://www.ashokleyland.com/in/lightvehicles/smallcommercialvechicles/bada-dost-i41/specification"
        ),
    ),
    VehicleReference(
        make="Ashok Leyland",
        model="Bada Dost i5+",
        fuel="Diesel",
        vehicle_category=VehicleCategory.pickup,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.flatbed,
        axle_count=2,
        payload_kg=2114,
        gvw_kg=3800,
        new_vehicle_price_anchor_inr=1_100_000,
        purpose_tags=["heavy_delivery", "construction", "industrial_goods"],
        spec_source_url=(
            "https://www.ashokleyland.com/in/lightvehicles/smallcommercialvechicles/bada-dost-i5-lx-2/specification"
        ),
    ),
    VehicleReference(
        make="Ashok Leyland",
        model="Bada Dost i6",
        fuel="Diesel",
        vehicle_category=VehicleCategory.pickup,
        weight_class=VehicleWeightClass.light,
        body_type=VehicleBodyType.open,
        axle_count=2,
        payload_kg=2357,
        gvw_kg=4100,
        new_vehicle_price_anchor_inr=1_200_000,
        purpose_tags=["heavy_delivery", "construction", "regional_delivery"],
        spec_source_url=(
            "https://www.ashokleyland.com/in/lightvehicles/smallcommercialvechicles/bada-dost-i6-lx/specification"
        ),
    ),
    # Heavy-vehicle base prices below are synthetic generation anchors. Published
    # GVW, configuration, and application data are linked on each reference.
    VehicleReference(
        make="Tata",
        model="Ultra T.16",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.medium,
        body_type=VehicleBodyType.container,
        axle_count=2,
        payload_kg=11_000,  # approx.; Tata publishes 11,040 kg for the closely matched 16.19T T.16
        gvw_kg=16_140,
        new_vehicle_price_anchor_inr=2_500_000,
        purpose_tags=["regional_delivery", "ecommerce", "fmcg", "industrial_goods"],
        spec_source_url="https://trucks.tatamotors.com/ultra/tata-ultra-t16",
    ),
    VehicleReference(
        make="Tata",
        model="Signa 4825.TK",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.tipper,
        axle_count=5,
        payload_kg=38_000,
        gvw_kg=47_500,
        new_vehicle_price_anchor_inr=6_000_000,
        purpose_tags=["mining", "construction", "coal", "aggregates"],
        spec_source_url=(
            "https://www.tatamotors.com/press-releases/"
            "tata-motors-introduces-indias-largest-tipper-truck-the-signa-4825-tk/"
        ),
    ),
    VehicleReference(
        make="Tata",
        model="Signa 4932.T",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.flatbed,
        axle_count=5,
        payload_kg=35_300,  # estimated from Tata's +1.3T payload claim vs comparable 47.5T haulage trucks
        gvw_kg=49_000,
        new_vehicle_price_anchor_inr=6_500_000,
        purpose_tags=["long_haul", "industrial_goods", "steel", "market_transport"],
        spec_source_url=("https://trucks.tatamotors.com/assets/trucks/files/2026-01/tata-signa-4932t.pdf"),
    ),
    VehicleReference(
        make="Mahindra",
        model="Furio 10",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.intermediate,
        body_type=VehicleBodyType.box,
        axle_count=2,
        payload_kg=6_000,
        gvw_kg=10_350,
        new_vehicle_price_anchor_inr=2_000_000,
        purpose_tags=["regional_delivery", "ecommerce", "fmcg", "parcel_delivery"],
        spec_source_url="https://www.mahindratruckandbus.com/english/pdf/icv/furio-10.pdf",
    ),
    VehicleReference(
        make="Mahindra",
        model="Blazo X 48",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.tipper,
        axle_count=5,
        payload_kg=32_000,  # estimated for 47.5T 29m3 tipper; official brochure does not publish payload
        gvw_kg=47_500,
        new_vehicle_price_anchor_inr=5_500_000,
        purpose_tags=["mining", "construction", "coal", "aggregates"],
        spec_source_url=("https://www.mahindratruckandbus.com/english/pdf/hcv/blazo_48_tipper.pdf"),
    ),
    VehicleReference(
        make="Ashok Leyland",
        model="AVTR 4825 10x2",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.tipper,
        axle_count=5,
        payload_kg=32_000,
        gvw_kg=47_500,
        new_vehicle_price_anchor_inr=5_900_000,
        purpose_tags=["construction", "coal", "aggregates", "roadwork"],
        spec_source_url=(
            "https://www.ashokleyland.com/in/pressrelease/"
            "ashok-leyland-launches-avtr-4825-10x2-tipper-with-tandem-dummy-axle"
        ),
    ),
    VehicleReference(
        make="Eicher",
        model="Pro 2118",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.medium,
        body_type=VehicleBodyType.flatbed,
        axle_count=2,
        payload_kg=12_800,
        gvw_kg=18_000,
        new_vehicle_price_anchor_inr=2_800_000,
        purpose_tags=["regional_delivery", "construction", "industrial_goods", "market_transport"],
        spec_source_url=("https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty/pro-2118"),
    ),
    VehicleReference(
        make="Eicher",
        model="Pro 6048T",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.tipper,
        axle_count=5,
        payload_kg=32_500,
        gvw_kg=47_500,
        new_vehicle_price_anchor_inr=5_600_000,
        purpose_tags=["mining", "construction", "coal", "aggregates"],
        spec_source_url=("https://www.eichertrucksandbuses.com/heavy-duty-trucks/tipper/pro-6048T"),
    ),
    VehicleReference(
        make="Eicher",
        model="Pro 6028TM",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.tipper,
        axle_count=3,
        payload_kg=16_500,
        gvw_kg=28_000,
        new_vehicle_price_anchor_inr=4_800_000,
        purpose_tags=["construction", "concrete", "infrastructure", "roadwork"],
        spec_source_url=("https://www.eichertrucksandbuses.com/heavy-duty-trucks/tipper/pro-6028tm-224kw"),
    ),
    VehicleReference(
        make="Eicher",
        model="Pro 6048XP",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.flatbed,
        axle_count=5,
        payload_kg=34_000,
        gvw_kg=47_500,
        new_vehicle_price_anchor_inr=5_300_000,
        purpose_tags=["long_haul", "industrial_goods", "steel", "market_transport"],
        spec_source_url=("https://www.eichertrucksandbuses.com/heavy-duty-trucks/haulage/pro-6048xp"),
    ),
    VehicleReference(
        make="BharatBenz",
        model="1917R",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.medium,
        body_type=VehicleBodyType.tanker,
        axle_count=2,
        payload_kg=10_000,
        gvw_kg=18_500,
        new_vehicle_price_anchor_inr=3_200_000,
        purpose_tags=["regional_delivery", "fuel_transport", "water_transport", "industrial_goods"],
        spec_source_url=("https://www.bharatbenz.com/trucks/mdt-specifications-1917r-73"),
    ),
    VehicleReference(
        make="BharatBenz",
        model="4828RT",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.tipper,
        axle_count=5,
        payload_kg=36_350,
        gvw_kg=47_500,
        new_vehicle_price_anchor_inr=5_800_000,
        purpose_tags=["mining", "construction", "coal", "aggregates"],
        spec_source_url="https://www.bharatbenz.com/uploads/truck_brochure/4828rt_74.pdf",
    ),
    VehicleReference(
        make="BharatBenz",
        model="3528C",
        fuel="Diesel",
        vehicle_category=VehicleCategory.rigid_truck,
        weight_class=VehicleWeightClass.heavy,
        body_type=VehicleBodyType.tipper,
        axle_count=4,
        payload_kg=20_600,
        gvw_kg=35_000,
        new_vehicle_price_anchor_inr=5_100_000,
        purpose_tags=["mining", "construction", "infrastructure", "aggregates"],
        spec_source_url=("https://www.bharatbenz.com/uploads/truck_brochure/3528c-truck.pdf"),
    ),
]
