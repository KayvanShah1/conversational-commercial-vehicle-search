# Vehicle Catalog Generation

This page is the repository overview. The wiki contains the complete [catalog-generation design](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Synthetic-Catalog-Generation), including distributions, pricing assumptions, schema, validation, provenance, and storage decisions.

## Purpose

The project uses a synthetic catalog of at least 100 used commercial-vehicle listings with:

- make and model
- year
- price
- kilometres driven
- fuel type
- payload or GVW
- body type
- city
- papers-verification status

The project generates this catalog instead of depending on a live marketplace dataset. This keeps the demo reproducible and gives the search layer enough controlled variation to test hard filters, ranking, and zero-result cases.

## Generation Approach

The generator starts from a curated set of commercial-vehicle references and creates synthetic used listings around them.

```mermaid
flowchart LR
    A[Vehicle References] --> B[Choose Weight Class]
    B --> C[Choose Compatible Model]
    C --> D[Generate Age + KM]
    D --> E[Generate Condition + Price]
    E --> F[Assign City + Verification]
    F --> G[Validate Listing]
    G --> H[Parquet / CSV]
    H --> I[MotherDuck]
```

Vehicle specifications are not generated independently. A selected model carries its compatible attributes such as:

- fuel
- payload/GVW
- vehicle category
- body type
- axle count
- intended-use tags

This avoids unrealistic combinations such as assigning arbitrary payloads or fuel types to a vehicle model.

The reference catalog contains source URLs for the commercial-vehicle specifications used during generation. Some pricing and heavy-vehicle payload values are explicitly treated as synthetic or derived anchors where authoritative values are unavailable. Estimated payloads remain searchable, but Vivi labels them as approximate rather than presenting them as manufacturer-published values.

## Synthetic Listing Fields

Once a vehicle reference is selected, listing-specific attributes are generated.

| Attribute | Generation |
|---|---|
| Year | Random vehicle age within the configured range |
| KM driven | Based on vehicle age and annual usage range |
| Condition | Weighted choice of `excellent`, `good`, or `fair` |
| Price | New-vehicle anchor adjusted for age, mileage, condition, and market noise |
| City | Weighted sampling across supported cities |
| Papers verified | Configurable probability |
| Listing ID | Deterministic generated identifier |
| Specification source URL | Link to official vehicle listing/ selected vehicle reference spec sheet|
| Payload basis | `payload_is_estimated` follows the selected reference and is shown with the value in agent responses and result cards |

Mileage is tied to vehicle age rather than sampled independently.

```text
km_driven ≈ age × annual_km × usage_variance
```

Price is calculated using an intentionally simple and inspectable depreciation model:

```text
used_price =
    new_price_anchor
    × age_factor
    × mileage_factor
    × condition_factor
    × market_noise
```

The goal is realistic search behavior, not used-vehicle price prediction.

## Tunable Parameters

The main generation settings can be changed without modifying generation logic.

| Parameter | Default |
|---|---:|
| Number of listings | 1000 |
| Random seed | 42 |
| Minimum vehicle age | 1 year |
| Maximum vehicle age | 12 years |
| Minimum annual usage | 8,000 km |
| Maximum annual usage | 35,000 km |
| Papers-verified probability | 0.82 |

Additional controlled assumptions include:

- vehicle weight-class distribution
- condition distribution
- depreciation rate
- mileage depreciation
- market-price variation
- city distribution

The fixed seed makes the generated catalog reproducible, which is useful for keeping search and evaluation results stable between runs.

## Output and Loading

The generator writes:

```text
data/generated/
├── vehicles.parquet
└── vehicles.csv
```

Parquet is used as the primary machine-readable artifact because it preserves column types and list-valued fields such as `purpose_tags`.

CSV is retained for quick inspection.

The Parquet catalog is loaded into:

```text
MotherDuck
└── vehicle_catalog
    └── vehicles
```

The catalog generator owns the write path. The search/agent layer only needs read access to the generated vehicle catalog.

## Validation

Pydantic models validate generated records, while the generator tests cover:

- reproducible output for the same seed
- coverage of the vehicle taxonomy
- configured weight-class distribution
- reference source availability
- valid Parquet and CSV serialization

This keeps the catalog predictable enough for hard-filter and evaluation requirements without adding a separate data-processing pipeline.

## Scope

The catalog is synthetic and intended only to support the voice-search system.

It does not attempt to reproduce actual used-commercial-vehicle inventory or market pricing. Manufacturer references are used to keep vehicle characteristics plausible, while listing-specific attributes such as age, mileage, price, city, condition, and verification status remain synthetic.
