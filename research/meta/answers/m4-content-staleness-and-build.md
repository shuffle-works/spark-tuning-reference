# Content, Staleness & Build

## Q1. What is the difference between a content page reported as ungenerated versus stale by content_state.py, and what should a human do in each case?

`content_state.py` distinguishes the two states by comparing a page's recorded hash in the committed sidecar `research/content-state.yaml` against the sha256 of the section projection it was assembled from[^architecture]. A page with no entry in that sidecar has never been generated from its section projection, and `content_state.py` reports it **ungenerated**[^runbook]. A page has an entry whose recorded hash no longer matches the current projection hash when the section's underlying answers changed since the page was generated or last accepted; `content_state.py` reports it **stale**[^architecture][^runbook].

The required human action differs accordingly. For an **ungenerated** page, the pipeline generates it: the answer-meta-question skill reads the page's `brief:` and `assembled_from:` entries from `content/meta/manifest.yaml`, writes the page from the projection, humanizes it, then runs `content_state --accept <page>` to stamp its hash[^skill-answer-meta-question]. For a **stale** page, nothing is overwritten automatically. The pipeline does not edit the page; a human hand-edits it to reflect the changed answers, and only then does `content_state.py --accept <page>` re-stamp the hash so the page is no longer flagged[^runbook][^architecture]. This follows from content pages being human-owned once generated: the pipeline never silently overwrites a generated page[^rules-content].

Both conditions are reported the same way, in CI rather than at build time (the HTML build that used to call this has since moved out of this repo entirely: see [^update-html] below). `scripts/prebuild_checks.py` runs per corpus (`.github/workflows/ci.yml`), calling `content_state.report(...)` and printing a non-fatal warning banner listing any stale/ungenerated pages[^architecture][^runbook]. Recompute never triggers first-gen on its own; it only ever flags a page stale, consistent with content pages staying human-owned once generated[^architecture].

## Q2. Why are content/manifest.yaml's anchor IDs described as a frozen cross-repo integration contract, and which sibling repository does that contract bind?

`content/manifest.yaml` is the single authority for section order, titles, and anchor IDs; content assembly reads anchors from it and never derives them from a Markdown heading or a filename[^rules-content][^anchor-map]. Because the anchors are looked up rather than generated from content, other repos can depend on them staying stable, so the project documents them as a frozen cross-repo Integration Contract with the sibling repo `sparkforensics`[^rules-content][^anchor-map]. Renaming or removing an anchor is a breaking change, and if the two repos' descriptions of an anchor diverge, the sibling repo's own contract doc wins[^rules-content].

The contract covers two sets of IDs: the 26 manifest-level anchors, one per `content/manifest.yaml` entry (enforced by `scripts/smoke_content.py`'s 26-section count check), and 4 config-page sub-anchors nested inside the single `config` manifest entry (`config-shuffle-service`, `config-autoscale-bounds`, `config-serializer`, `config-memory-overhead`). These four aren't manifest entries themselves but are also enforced by `scripts/smoke_content.py`[^rules-content]. The contract applies only to `content/manifest.yaml`/`index.html`, i.e. the Spark corpus; `content/meta/manifest.yaml` and `meta.html` carry no such contract, so this meta corpus's own anchors may change freely[^rules-content].

## Q3. What does build.py do when it detects a stale or ungenerated content page, and why is that warning non-fatal?

`build.py`'s HTML-generation role has since been retired twice over. First the site build moved from that single Python script (Jinja2 + python-markdown) to a Node pipeline (`site/build-chapters.mjs`, one committed HTML page per manifest entry, per corpus, under `chapters/<spark|meta>/<anchor>.html`)[^architecture][^adr-vite]; that Node pipeline has since also been retired, and HTML generation has moved out of this repo entirely, to whichever repo consumes `content/*.md`[^update-html]. The RAG answering pipeline itself (the registry, per-question answers, section projections, and the staleness model) stayed Python through both moves[^architecture].

`scripts/prebuild_checks.py` (originally split out of `build.py`'s former inline flow so the Node build could shell out to it) now runs standalone, per corpus, in CI (`.github/workflows/ci.yml`)[^update-html]. It calls `content_state.report(...)` and prints the same non-fatal warning banner listing any stale/ungenerated pages, classifying each as ungenerated (no recorded entry), stale (hash differs), or up to date (hash matches)[^architecture][^runbook].

The warning stays non-fatal for the same reason it always was: content pages are human-owned once generated, and the pipeline never overwrites a page's prose automatically, even when its upstream answers have changed[^architecture]. A stale or ungenerated flag just means the built page's text may not reflect the latest answers yet. Fixing it requires a human to edit the page (or run first-gen for an ungenerated one) and then re-stamp its hash with `content_state.py --accept <page>` so it reports up to date again[^runbook][^architecture]. Recompute itself never triggers first-gen; it only ever flags a page stale, so content pages stay human-owned[^architecture].

## Sources

[^architecture]: architecture — references-meta/docs/architecture.md
[^runbook]: runbook — references-meta/docs/runbook.md
[^skill-answer-meta-question]: skill-answer-meta-question — references-meta/skills/answer-meta-question.md
[^rules-content]: rules-content — references-meta/docs/rules/content.md
[^update-html]: update-html — references-meta/docs/architecture.md's "HTML generation" section (added after this answer was drafted: the Node build this answer originally described has itself since been retired, and this repo no longer renders HTML at all).
[^anchor-map]: anchor-map — references-meta/docs/anchor-map.md
[^adr-vite]: adr-vite — references-meta/docs/adr/0006-vite-site-build.md (docs/adr/ was removed; this rationale now lives in docs/architecture.md's Staleness model section. Left as a historical citation, not rewritten, since this is pipeline-generated research output rather than hand-authored prose.)
