# Content, Staleness & Build

## Ungenerated vs. stale

`content_state.py` distinguishes the two states by comparing a page's recorded hash in the committed sidecar `research/content-state.yaml` against the sha256 of the section projection it was assembled from[^architecture]. A page with no entry in that sidecar has never been generated from its section projection, and `content_state.py` reports it **ungenerated**[^runbook]. A page has an entry whose recorded hash no longer matches the current projection hash when the section's underlying answers changed since the page was generated or last accepted; `content_state.py` reports it **stale**[^architecture][^runbook].

The required human action differs accordingly. For an **ungenerated** page, the pipeline generates it: the answer-meta-question skill reads the page's `brief:` and `assembled_from:` entries from `content/meta/manifest.yaml`, writes the page from the projection, humanizes it, then runs `content_state --accept <page>` to stamp its hash[^skill-answer-meta-question]. For a **stale** page, nothing is overwritten automatically. The pipeline does not edit the page; a human hand-edits it to reflect the changed answers, and only then does `content_state.py --accept <page>` re-stamp the hash so the page is no longer flagged[^runbook][^architecture]. This follows from content pages being human-owned once generated: the pipeline never silently overwrites a generated page[^rules-content].

## Anchors as a frozen cross-repo contract

`content/manifest.yaml` is the single authority for section order, titles, and anchor IDs; content assembly reads anchors from it and never derives them from a Markdown heading or a filename[^rules-content][^anchor-map]. Because the anchors are looked up rather than generated from content, other repos can depend on them staying stable, so the project documents them as a frozen cross-repo Integration Contract with the sibling repo `sparkforensics`[^rules-content][^anchor-map]. Renaming or removing an anchor is a breaking change, and if the two repos' descriptions of an anchor diverge, the sibling repo's own contract doc wins[^rules-content].

The contract covers two sets of IDs: the 31 manifest-level anchors, one per `content/manifest.yaml` entry (enforced by `scripts/smoke_content.py`'s 31-section count check), and 12 sub-anchors nested inside a manifest entry's own page rather than being manifest entries themselves: 4 config-page sub-anchors inside the single `config` entry (`config-shuffle-service`, `config-autoscale-bounds`, `config-serializer`, `config-memory-overhead`) and 8 detector-facing sub-anchors: `bottleneck-stage-shape` and `bottleneck-stage-slowness` inside the `bottleneck-skew` and `bottleneck-slow-host` entries, `bottleneck-partition-sizing` inside `bottleneck-shuffle`, `bottleneck-cache-utilization` inside `memory-model`, `bottleneck-core-locality` and `bottleneck-caching-opportunity` inside `bottleneck-utilization`, `bottleneck-speculation-waste` inside `bottleneck-straggler`, and `bottleneck-autoscaling-churn` inside `cluster-config`. All 12 are also enforced by `scripts/smoke_content.py`[^rules-content]. The contract applies only to `content/manifest.yaml`/`index.html`, i.e. the Spark corpus; `content/meta/manifest.yaml` and `meta.html` carry no such contract, so this meta corpus's own anchors may change freely[^rules-content].

## HTML generation, retired from this repo

`build.py`'s HTML-generation role has since been retired twice over. First the site build moved from that single Python script (Jinja2 + python-markdown) to a Node pipeline (`site/build-chapters.mjs`, one committed HTML page per manifest entry, per corpus, under `chapters/<spark|meta>/<anchor>.html`)[^architecture][^adr-vite]; that Node pipeline has since also been retired, and HTML generation has moved out of this repo entirely, to whichever repo consumes `content/*.md`[^update-html]. The RAG answering pipeline itself (the registry, per-question answers, section projections, and the staleness model) stayed Python through both moves[^architecture].

`scripts/prebuild_checks.py` (originally split out of `build.py`'s former inline flow so the Node build could shell out to it) now runs standalone, per corpus, in CI (`.github/workflows/ci.yml`)[^update-html]. It calls `content_state.report(...)`, compares each content page's recorded hash (from `research/content-state.yaml`) against the current section-projection hash, and classifies the page as ungenerated (no recorded entry), stale (hash differs), or up to date (hash matches), printing a non-fatal warning banner listing any that aren't[^architecture][^runbook].

The warning is non-fatal because content pages are human-owned once generated: the pipeline never overwrites a page's prose automatically, even when its upstream answers have changed[^architecture]. A stale or ungenerated flag just means the page's text may not reflect the latest answers yet. Fixing it requires a human to edit the page (or run first-gen for an ungenerated one) and then re-stamp its hash with `content_state.py --accept <page>` so it reports up to date again[^runbook][^architecture]. Recompute itself never triggers first-gen; it only ever flags a page stale, so content pages stay human-owned[^architecture].

## Sources

[^architecture]: architecture — references-meta/docs/architecture.md
[^runbook]: runbook — references-meta/docs/runbook.md
[^skill-answer-meta-question]: skill-answer-meta-question — references-meta/skills/answer-meta-question.md
[^rules-content]: rules-content — references-meta/docs/rules/content.md
[^update-html]: update-html — references-meta/docs/architecture.md's "HTML generation" section (added after this page was first generated: the Node build it originally described has itself since been retired, and this repo no longer renders HTML at all).
[^anchor-map]: anchor-map — references-meta/docs/anchor-map.md
[^adr-vite]: adr-vite — references-meta/docs/adr/0006-vite-site-build.md (docs/adr/ was removed; this rationale now lives in docs/architecture.md's Staleness model section.)
