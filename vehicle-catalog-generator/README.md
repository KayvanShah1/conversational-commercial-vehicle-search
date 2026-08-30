# Vehicle Catalog Generator

Generates a deterministic synthetic commercial-vehicle catalog in Parquet and CSV formats, then optionally loads it into MotherDuck.

Run generation from the workspace root:

```powershell
uv run python -m vehicle_catalog_generator.generator
```

Load the catalog into MotherDuck:

```powershell
uv run python -m vehicle_catalog_generator.load
```

Copy `example.env` to `.env`, configure `MOTHERDUCK__TOKEN`, and set `DATA_GENERATION__REPLACE=true` when existing generated files should be replaced before loading.
