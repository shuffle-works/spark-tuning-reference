# Architecture

Normative rules for each pipeline stage live in `docs/rules/` (`registry.md`,
`research.md`, `editorial.md`, `content.md`), not here. This doc explains the
shape of the pipeline, not what's mandatory within a stage.

## Answering pipeline (question-granular)

The atomic unit of the answering pipeline is the **question**, not the section.
`research/questions.yaml` is the single source of truth: it holds `sections`
(id, num, title, default_k) and `questions` (id, section, text, version, k,
status). Every other artifact is a derived projection, regenerable from the
registry and the per-question answer files, never edited as a source of truth
itself.

### Derive direction (one-way)

```
research/questions.yaml
        │  (registry: sections + questions, statuses)
        ▼
research/answers/q/<id>.md
        │  (per-question answer: prose + [^id] footnotes + own ## Sources)
        ▼
research/answers/<section-id>.md
        │  (section projection: ordered concat of a section's question
        │   answers, Sources merged + deduped; same path the manifest's
        │   `assembled_from:` already points at)
        ▼
content/*.md, content/bottlenecks/*.md
        │  (brief-driven, first-gen only; human-owned after that)
        ▼
content/manifest.yaml → anchors.json (scripts/build_anchors.py)
```

The pipeline in this repo ends at `content/*.md` + `content/manifest.yaml` +
the derived `anchors.json`. Rendering that content to HTML happens upstream,
in a separate repo (see "HTML generation" below).

Every arrow is one-way. A downstream artifact (a section projection, a content
page) is never a source of truth for an upstream one. Recompute always starts
at `questions.yaml` and flows forward.

### Deterministic scripts vs. agents

Plumbing that has a single correct answer given its inputs is a deterministic,
pytest-covered script under `scripts/`:

- `scripts/registry.py`: load/save/validate `questions.yaml` (`Registry`,
  `Section`, `Question` dataclasses).
- `scripts/add_question.py`: append-only. Mint an id, append a `pending`
  record, never mutate existing records.
- `scripts/recompute_question.py`: flip one record to `pending`, back up its
  old answer file, touch nothing else.
- `scripts/project_section.py`: rebuild a section's projection by
  concatenating its questions' answer files in registry order and merging
  their `## Sources` blocks.
- `scripts/content_state.py`: report each content page as
  ungenerated/stale/ok by comparing its recorded hash against the current
  section-projection hash; `--accept <page>` stamps the hash. It never writes
  page prose.
- `scripts/list_pending.py`: print ids with `status: pending`. Drives batch
  runs (replaces the deleted `step4-answering.js`'s `SECTIONS` loop).
- `scripts/check_prose.py`: no-LLM lint/backstop for the Humanize stage. Flags
  leftover AI-tell vocabulary and structural tics, bans curly quotes and em
  dashes, and (`--diff`) checks footnotes/`## Sources`/markers/heading/numbers
  survived a humanize pass unchanged. See `docs/rules/editorial.md` #2.

Everything that requires judgment stays an agent: retrieval, drafting,
verifying citations, fixing issues, humanizing prose, first-generating a
content page from a brief. Those agents are `spark-section-draft`,
`spark-section-verify`, `spark-section-redraft` (each now scoped to a single
question) and the `writing-prose-like-a-human-for-agents:prose-humanizer`
agent (installed plugin). The `answer-question` skill
(`.claude/skills/answer-question/SKILL.md`) runs one question end to
end: Draft → Verify → [Redraft → re-Verify] → Humanize → `check_prose` →
`project_section` → `content_state` (first-gen or flag-stale) → commit.

### Staleness model

`research/content-state.yaml` is a committed hash sidecar mapping each
content page to the sha256 of the section projection it was last generated or
accepted from. `content_state.py` compares that recorded hash against the
current projection hash:

- no entry → **ungenerated** (the skill runs first-gen, then `--accept`)
- hash differs → **stale** (nothing is overwritten; a human edits the page,
  then `--accept` re-stamps the hash)
- hash matches → **ok**

`scripts/prebuild_checks.py` runs per corpus in CI (`.github/workflows/ci.yml`):
manifest-mapping validation first (fatal), then `content_state.report(...)`,
which prints a non-fatal warning banner listing any stale/ungenerated pages.
Recompute never triggers first-gen: it only ever flags a page stale, since
content pages are human-owned once generated.

### HTML generation

This repo does not render HTML. That responsibility moved through two prior
homes: a single Python script (`build.py`, Jinja2 plus python-markdown), then
a Node pipeline (`site/build-chapters.mjs`, one committed page per manifest
entry per corpus). It has since moved out of this repo entirely, into the
repo that consumes the content. `scripts/smoke_content.py` and
`tests/test_links.py` check the invariants a renderer needs (anchor coverage,
footnote resolution, blockquote-fence safety, intra-page link resolution)
directly against `content/*.md`, so a violation is caught here before any
downstream renderer sees the content.

The one artifact this repo still emits for a consumer is `anchors.json`
(`scripts/build_anchors.py`): a faithful, keyword-populated
projection of `content/manifest.yaml` that `sparkforensics`' detector-coverage
check reads (see `docs/anchor-map.md`). How the upstream renderer fetches
`content/*.md` itself is that repo's concern, not this one's.

### Diagrams

Content pages embed diagrams as SVGs under `content/diagrams/`. Each diagram's
source of truth is a Mermaid `.mmd` file; `scripts/render_diagrams.py` compiles it
to a committed light and dark SVG pair, and pages link both as a `light-only`/
`dark-only` `<img>` pair so the upstream renderer's theme toggle picks the right
one. Rendering is offline and Python-only (the `mermaidx` package runs the real
mermaid.js in an embedded JS engine, declared inline via PEP 723 so it never enters
this repo's dependency tree). The palette lives in the render script, so `.mmd`
sources carry structure and labels only. See `docs/runbook.md` for the workflow and
`docs/rules/content.md` for the invariants; serving the SVG asset files to a browser
is the consuming renderer's job, as with `content/*.md`.

## Corpora

The pipeline shape above (registry question → RAG draft/verify/redraft →
section projection → content page → build) is used by two independent
corpora, selected via `--corpus {spark,meta}` on every pipeline script
(default `spark`). `scripts/corpus.py` holds the `Corpus` dataclass and the
`SPARK`/`META` profiles. Every path a script touches comes from the selected
profile, never a hardcoded module constant: registry, per-question answers
dir, section-projection dir, content-state sidecar, content manifest,
references dir, Chroma path/collection, embedding model, build output, site
title.

`spark` (the default) is this Spark Tuning Reference, over
`references/`, indexed with the asymmetric question→passage retriever
`multi-qa-mpnet-base-dot-v1`, producing the pages under `content/`.

`meta` is this project's own architecture doc: this file, `docs/runbook.md`,
`docs/rules/*.md`, `AGENTS.md`, and the agent/skill files that make up the
pipeline. It is indexed via symlinks under `references-meta/` with the general
symmetric model `all-mpnet-base-v2` into a separate Chroma collection
(`meta_docs` in `.chromadb-meta/`), over its own
`research/meta/questions.yaml` registry and `content/meta/manifest.yaml`,
producing the pages under `content/meta/`. It is answered by the `meta-section-draft`/
`meta-section-verify`/`meta-section-redraft` agents and the
`answer-meta-question` skill: mirrors of `spark-section-*` and
`answer-question`, adapted to the meta corpus's paths and `--corpus meta`
invocations, not shared prompt text. The two corpora never share a registry,
a Chroma collection, or a content manifest. Each is an independent instance of
the same pipeline shape.
