# Spark tuning reference

An evidence-first reference for optimizing Apache Spark and PySpark jobs. Start from a job symptom, find the Spark mechanism behind it, then pick a tuning lever worth testing. The point is to stop hunches from becoming production settings.

The published site covers Spark internals, memory, partitioning, joins, shuffle, file and table formats, caching, PySpark, AQE, cluster tuning, recurring anti-patterns, a bottleneck detector catalog, metrics, and configuration defaults.

## How to use it

1. Observe. Spark already reports plan details, plus metrics per stage and per executor. [SparkForensics](https://github.com/shuffle-works/sparkforensics) can help surface them from an event log.
2. Explain. Follow the reference from the symptom to the mechanics behind it: memory, shuffle, joins, AQE, or configuration.
3. Test. Change one lever, rerun the workload, and compare the evidence instead of carrying a tuning superstition forward.

The two tools split the work on purpose. SparkForensics reads event logs; this project explains the mechanics and settings behind the findings.

## Read it locally

`content/` holds the reference itself, plain Markdown: start at `content/01-intro.md`
and follow the section files in `content/manifest.yaml`'s order, or jump straight
to a bottleneck under `content/bottlenecks/`.

This repo does not render HTML. Turning `content/*.md` into a browsable site
happens in a separate, upstream repo; see the "HTML generation" section of
`docs/architecture.md` for how that split works.

## Project map

- `content/`: human-facing reference pages and bottleneck entries.
- `content/manifest.yaml`: navigation order, stable published anchors, and content mappings.
- `anchors.json`: a generated projection of `manifest.yaml`, published for `sparkforensics`'s detector-coverage check.
- `research/`: question registry, cited answers, and content-staleness state.
- `references/`: source corpus used for research and retrieval.
- `docs/architecture.md`: the question-granular research pipeline, and where HTML rendering now lives.
- `docs/runbook.md`: how to add and recompute content, and how to accept it.

Stable anchors in the manifest are an integration contract with SparkForensics. Treat a rename or removal as a breaking change.

## Development

You need Python 3.11+ and [uv](https://docs.astral.sh/uv/). The default
dependencies cover the core tests and content checks:

```bash
uv sync --group dev
uv run --group dev python -m pytest
uv run scripts/check_prose.py content
uv run scripts/smoke_content.py
```

Retrieval and MCP support live in optional dependency groups. See the [runbook](docs/runbook.md) for setup and operating procedures, and [the architecture](docs/architecture.md) for the pipeline's source-of-truth and staleness rules.
