# Vivi evaluations

This workspace package owns the executable evaluation harnesses, their configuration, and the checked-in case datasets.

```text
evals/
├── datasets/
│   ├── agent_cases.json
│   ├── vehicle_variant_cases.json
│   └── voice/
│       ├── voice_cases.json
│       └── *.wav
└── src/evals/
    ├── evaluator/
    │   ├── agent.py
    │   ├── voice.py
    │   └── voice_metrics.py
    ├── reporting/
    │   ├── core.py
    │   └── voice.py
    └── settings.py
```

Run the core conversation suite first:

```powershell
uv run --package evals python -m evals.evaluator.agent --delay-seconds 10
```

Then run the vehicle breadth suite:

```powershell
uv run --package evals python -m evals.evaluator.agent `
  --cases evals/datasets/vehicle_variant_cases.json `
  --delay-seconds 10
```

Run the recorded voice suite only with audio you are authorized to send to the configured speech provider:

```powershell
uv run --package evals python -m evals.evaluator.voice --delay-seconds 10
```

Add another case by placing its WAV beside `voice_cases.json` and adding the reference utterance, expected action, and expected filters to that manifest. Cases with the same `conversation_id` share state and must remain in turn order.

JSON and Markdown reports are written locally under `data/evaluation/` and excluded from Git. The five newest runs are retained automatically, including reports written with a custom `--output` name. See the repository [evaluation guide](../docs/EVALUATION.md) for scoring, metrics, and interpretation.

Agent reports separate routing accuracy, tool-only accuracy, no-tool accuracy, argument/state accuracy, and the end-to-end pass rate. Voice reports add transcript exact match, word and character error rates, filter precision/recall/F1, and mean, p50, and p95 stage latency. `expected_action` remains each case's single routing label.
