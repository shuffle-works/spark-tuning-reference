# Content rules

Rules for `content/*.md` pages and `content/manifest.yaml`, this repo's entire
deliverable. HTML rendering happens upstream (`docs/architecture.md`'s "HTML
generation" section). Data model and pipeline shape: `docs/architecture.md`.

## Rules

1. **Every factual/numeric/config claim needs a citation**, sourced via the local RAG
   pipeline over `references/` (see `docs/rules/research.md` for how the answering
   pipeline produces one). Never add an uncited numeric/config claim to a content page.
   When a content page is humanized (`.claude/skills/answer-question/SKILL.md` step 8),
   `scripts/check_prose.py --diff <before> <after>` (see `docs/rules/editorial.md` #2)
   checks that footnotes and numeric tokens survived the pass unchanged.

2. **`content/manifest.yaml` is the single authority for section order, titles, and
   anchor IDs.** Anchors must never be derived from Markdown heading text or filenames:
   always read them from the manifest (`docs/anchor-map.md` reconciles manifest
   anchors against the research answer files they're assembled from).

3. **Anchor IDs are a frozen cross-repo Integration Contract** with
   `sparkforensics`: renaming or removing one is a breaking change, and that
   sibling repo's own contract doc wins on divergence. This applies ONLY to
   `content/manifest.yaml` (the Spark corpus); `content/meta/manifest.yaml`
   carries no such contract and its anchors may change freely. This covers:
   - the 31 manifest-level anchors (one per `content/manifest.yaml` entry, enforced by
     `scripts/smoke_content.py`'s 31-section count check), and
   - 12 sub-anchors that live inside a manifest entry's own page and so aren't manifest
     entries themselves, enforced by `scripts/smoke_content.py`'s separate `SUB_ANCHORS`
     check: 4 config-page sub-anchors nested inside the single `config` entry
     (`config-shuffle-service`, `config-autoscale-bounds`, `config-serializer`,
     `config-memory-overhead`), plus 8 detector-facing sub-anchors, each nested inside
     an existing bottleneck or chapter page instead of getting its own manifest entry,
     because the page it would otherwise share never discussed its specific signal:
     `bottleneck-stage-shape`/`bottleneck-stage-slowness` (nested inside
     `bottleneck-skew`/`bottleneck-slow-host`; `SHAPE` used to link to Task Skew,
     covering only one of its three smells, and `SLOW` used to link to Slow Host, a
     case its own detector explicitly rules out), `bottleneck-partition-sizing` (nested
     inside `bottleneck-shuffle`), `bottleneck-cache-utilization` (nested inside
     `memory-model`), `bottleneck-core-locality`/`bottleneck-caching-opportunity`
     (nested inside `bottleneck-utilization`), `bottleneck-speculation-waste` (nested
     inside `bottleneck-straggler`), and `bottleneck-autoscaling-churn` (nested inside
     `cluster-config`); see `docs/anchor-map.md`'s coverage-contract section for how
     sparkforensics' doc-anchor coverage check treats these against `anchors.json`.

   Adding or removing a content page changes the 31-section count `smoke_content.py`
   asserts: update that literal in the same change. Note `anchors.json`
   projects only the manifest-level anchors, not these 12 sub-anchors; see
   `docs/anchor-map.md`'s coverage-contract section for why that's a known,
   documented gap in the machine-readable contract, not an oversight here.

4. **A rendered fenced-code block nested inside a blockquote is unreliable across
   Markdown renderers** (some leave the ` ``` ` markers as literal text). PySpark
   callout blockquotes needing code must use inline `` `code` `` only; multi-line
   snippets go in a fenced block placed after the blockquote, not inside it.
   Enforced by `scripts/smoke_content.py`'s blockquote scan over the source.

5. **Theme is the upstream renderer's concern, not this repo's.** This repo commits
   no HTML, CSS, or client-side script, so it makes no claim about how a rendered
   page controls or persists a light/dark theme.

6. **Content pages are human-owned once generated**: the pipeline never overwrites one
   silently. After an upstream answer changes, `content_state.py` flags the page
   `stale`; a human edits it, then `scripts/content_state.py --accept <page>` re-stamps
   its hash. See `docs/architecture.md`'s staleness model and `docs/runbook.md` for the
   accept workflow.

7. **Cross-referencing another manifest entry from content prose still uses `[text](#anchor)`.**
   Write the link as `#anchor` in Markdown and let the upstream renderer resolve it to
   wherever it puts that entry (its own page, an in-page id, or something else); don't
   assume a particular target shape here. Anything else starting with `#` (a footnote
   ref, a sub-anchor heading `{#id}` inside the *same* entry) is left as a same-page
   fragment, since it isn't a manifest anchor. `tests/test_links.py` checks every such
   link resolves to either a real manifest anchor or a same-file `{#id}`.

8. **Diagrams are Mermaid sources compiled to committed SVGs.** A diagram's source
   of truth is `content/diagrams/<name>.mmd`; `scripts/render_diagrams.py` renders it
   to `<name>.svg` (light) and `<name>.dark.svg` (dark), and a page links both as a
   `light-only`/`dark-only` `<img>` pair, one plain `<img>` tag each rather than a
   `<picture>`/`<source media="prefers-color-scheme">` element, so the upstream
   renderer's own theme toggle can pick the right one instead of only tracking the
   OS setting. Keep `.mmd` sources colour-free (structure and labels only): the
   palette lives in the render script and is applied to both themes there.
   Regenerate the SVGs after any `.mmd` edit (`docs/runbook.md`). Serving the
   `content/diagrams/` asset files and wiring the `light-only`/`dark-only` CSS to the
   toggle are the consuming renderer's job, not this repo's.

See also `docs/rules/editorial.md` for prose-style rules and `docs/rules/research.md`
for retrieval/citation mechanics during answering.
