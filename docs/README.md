# Documentation

Repository documentation is organized around common reviewer and developer tasks. For deeper implementation narratives, use the [project wiki](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki).

| Goal | Document |
| --- | --- |
| Install dependencies, configure providers, and run Vivi | [Setup](SETUP.md) |
| Review the source brief and scoring rubric | [Original specification](assignment/README.md) and [PDF](assignment/voice-search-assignment.pdf) |
| Understand architecture, boundaries, and trade-offs | [Technical decisions](TECHNICAL_DECISIONS.md) |
| Inspect evaluation coverage, results, latency, and cost | [Evaluation](EVALUATION.md) |
| Map each requirement to implementation evidence | [Requirements checklist](SUBMISSION_CHECKLIST.md) |
| Review the synthetic catalog at a practical level | [Catalog generation](DATA_GENERATION.md) |
| Audit external libraries, providers, and references | [Sources](SOURCES.md) |

## Directory map

```text
docs/
├── README.md
├── SETUP.md
├── TECHNICAL_DECISIONS.md
├── EVALUATION.md
├── SUBMISSION_CHECKLIST.md
├── DATA_GENERATION.md
├── SOURCES.md
├── assignment/
│   ├── README.md
│   └── voice-search-assignment.pdf
└── assets/
    ├── repo-cover-prompt.txt
    └── vivi-ui-concept.png
```

Generated evaluation reports are stored under `data/evaluation/`. Executable harnesses remain under `evals/`, and their case files are grouped under `evals/datasets/`.

The repository-cover generation brief is retained as [`assets/repo-cover-prompt.txt`](assets/repo-cover-prompt.txt) for provenance.
