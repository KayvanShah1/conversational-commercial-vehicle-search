# Vivi evaluations

This workspace package owns the executable evaluation harnesses, their configuration, and the checked-in case datasets.

```text
evals/
├── datasets/
│   ├── agent_cases.json
│   └── vehicle_variant_cases.json
└── src/evals/
    ├── evaluate_agent.py
    ├── measure_voice_latency.py
    ├── reporting.py
    └── settings.py
```

Run the core conversation suite first:

```powershell
uv run --package evals python -m evals.evaluate_agent --delay-seconds 10
```

Then run the vehicle breadth suite:

```powershell
uv run --package evals python -m evals.evaluate_agent `
  --cases evals/datasets/vehicle_variant_cases.json `
  --delay-seconds 10
```

Run a real voice turn only with audio you are authorized to send to the configured speech provider:

```powershell
uv run --package evals python -m evals.measure_voice_latency `
  --audio path/to/authorized-sample.wav
```

JSON and Markdown reports are written locally under `data/evaluation/` and excluded from Git. The five newest runs are retained automatically, including reports written with a custom `--output` name. See the repository [evaluation guide](../docs/EVALUATION.md) for scoring, metrics, and interpretation.

Each report separates routing accuracy, tool-only accuracy, no-tool accuracy, argument/state accuracy, and the end-to-end pass rate. Argument/state accuracy checks the expected filters and changed slots for tool-using cases. `expected_action` remains the dataset's single routing label; the report does not duplicate it with a second expected-tool field.
