# Spark Tuning Reference

Static Spark/PySpark performance-tuning reference site, embedded via iframe by a sibling `sparkforensics` app.

## Directory Standard
- `docs/` holds only project docs (architecture, runbook, rules) — never research results or the registry. Research artifacts (`questions.yaml`, `content-state.yaml`, per-question/section answers) live under top-level `research/`.
- All project rules live under `docs/rules/`, one file per pipeline stage — never copy-pasted inline into an agent file or into this file. An agent/human consults the relevant `docs/rules/*.md` file(s) directly; this file only points to them.
- A second, independent pipeline instance (corpus `meta`) documents this project's own architecture, over `research/meta/`, `content/meta/`, `references-meta/` — see `docs/architecture.md`'s Corpora section, not restated here.

## Non-Obvious Rules
- The answering pipeline has run: every `content/*.md` page is real cited prose (human-owned once generated), not a placeholder. `research/questions.yaml` remains the authoritative question registry (not the research-plan prose or a `SECTIONS` array); answers are per-question (`research/answers/q/<id>.md`) projected into the section files (`research/answers/<section-id>.md`), which content pages assemble from; see `docs/architecture.md`. New/changed content still flows registry → answer → projection → page.

## Key Documents
- Architecture, data model, and answering pipeline (the "what"): `docs/architecture.md`
- Architectural rationale (the "why"): kept directly in the doc it's most relevant to, whether that's `docs/architecture.md`, a runbook section, an anchor-map entry, or an inline code comment, rather than in a separate ADR log.
- Operator procedures (add/answer/recompute questions, build): `docs/runbook.md`
- Answer-file ↔ manifest-anchor reconciliation: `docs/anchor-map.md`
- Rules, one file per pipeline stage — `docs/rules/`:
  - Registry (`research/questions.yaml`) invariants: `docs/rules/registry.md`
  - Retrieval/citation rules for the Draft/Verify/Redraft agents: `docs/rules/research.md`
  - Prose/editorial rules for answers and content: `docs/rules/editorial.md`
  - Content-page and build invariants (anchors, manifest authority, theme contract): `docs/rules/content.md`

<!-- graft:start -->
## Graft — repo context graph

This repo is indexed in `graft/`: small linked markdown nodes that explain each
system and carry exact file:line spans, kept in sync with the code through git.

For ANY task here — understanding how something works, finding where code lives,
or scoping a change — get context from the graph before grepping or opening
source files. Re-ask freely (it's cheap) and reuse literal identifiers you
already have (symbol, error string, file name) as the query. New to this repo?
Run `graft map` first — a token-budgeted orientation (dir clusters, hubs,
hotspots), no LLM, no key.

- Run `graft ask "<your question>" --source` → ranked nodes with the relevant
  code spans inlined (each hit's ≤8-line crux by default; `--full` for whole
  definitions when the crux isn't enough). Match the tool to the task shape:
  for understanding or editing, the top node IS the answer — cite its
  `covers:` file:line spans and edit straight from `--source`. For
  exhaustive tasks ("every occurrence / every caller of this pattern"), ranked
  results are top-N, not complete — run `graft grep "<literal>"` instead
  (exhaustive over indexed files, grouped by enclosing symbol), falling back
  to raw `grep -rn` only for unindexed files.
- `graft skeleton <file>` → every definition's signature + span, ~10× cheaper
  than reading the file; use it to skim an API surface.
- `graft callers <symbol>` gives precomputed, exact edges — who calls this.
  Add `--direction out` for what it calls, or `--depth N` to walk
  transitively for the full blast radius. For structural questions, skip
  ranking and use this directly.
- Or browse: `graft/INDEX.md` lists every node; follow the links.
- Monorepos and folders of multiple repos rank fairly across sub-projects —
  hits carry `[scope/]` labels naming which one they're from. Narrow with
  `graft ask "<task>" --in <scope>/` once you know where you're working.

If a returned span is truncated ("+N more lines"), open the file at that exact
range before finalizing. Only open source files when a node genuinely lacks a
needed detail, and then at the exact file:line the node points to — never
re-read whole files.

After big code changes, refresh the graph with `graft build` (deterministic,
no API key, $0).
<!-- graft:end -->
