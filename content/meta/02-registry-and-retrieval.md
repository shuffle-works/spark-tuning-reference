# Registry & Retrieval

## The registry's data model

`research/questions.yaml` holds two top-level collections. A section record has `id`, `num`, `title`, and `default_k`. A question record has `id`, `section`, `text`, `version`, `k`, and `status`[^architecture].

`id` is stable once minted: `scripts/add_question.py` appends a new `pending` record and prints its id[^runbook], but never mutates an existing record's `id`, `section`, or `text`. A reworded or dropped question gets a new id rather than a rewritten one[^rules-registry].

`version` is one of `3.0` / `3.5` / `4.0` / `n/a`, passed through to `ask.py --version`[^rules-registry]. It has a default rather than being absent: `add_question` takes an optional `--version X` flag and falls back to `n/a` when omitted[^runbook]. The meta corpus's own registry (`research/meta/questions.yaml`) doesn't use the bucket concept at all. Every question there is `n/a`[^agent-meta-draft].

`k` is the field that's genuinely optional at the per-question level: `add_question` takes an optional `--k N` that overrides the section's `default_k` for that one question only; when a question's `k` is left null, the answering pipeline reads the section's `default_k` instead[^skill-answer-question].

`status` starts as `pending` on append and is later flipped by the answering pipeline to `answered` if verification passes with no unresolved markers, or `needs-review` otherwise[^skill-answer-question]. `scripts/recompute_question.py` can also flip an existing record's status back to `pending` while backing up its old answer file, without touching any other record or file[^rules-registry].

## Why retrieval differs by corpus

For the Spark corpus (the `spark` profile, `scripts/ask.py`'s default), retrieval is indexed over `references/` with `multi-qa-mpnet-base-dot-v1`, which the architecture doc itself labels "the asymmetric question→passage retriever"[^architecture]. That label is contrasted directly with the other corpus this pipeline runs: the meta corpus (this doc's own corpus) uses a different, symmetric embedding model, `all-mpnet-base-v2`, instead[^architecture]. The research rules single out `multi-qa-mpnet-base-dot-v1`'s asymmetric, question-to-passage nature as the reason the retriever's absolute similarity scores run low. Relevance is computed as `2·cos − 1`, so rank matters more than the raw number[^rules-research]. That's also why the gap-marking gate for Spark-corpus drafting tells writers not to mark a claim `[UNRESOURCED]` just because a retrieved chunk's relevance score is low or slightly negative: with this asymmetric model, a positive-or-slightly-negative-relevance chunk can still visibly answer the question and should be extracted, and `[UNRESOURCED]` is reserved for when no retrieved chunk supports any part of the answer at all[^rules-research].

The two corpora are selected via `--corpus {spark,meta}` on every pipeline script, and `scripts/corpus.py`'s `Corpus` dataclass keeps every path and setting for each profile fully separate: registry, per-question answers dir, section-projection dir, content-state sidecar, content manifest, references dir, Chroma path/collection, embedding model, build output, and site title all come from the selected profile rather than a hardcoded constant[^architecture]. The Spark corpus is indexed with the asymmetric question→passage retriever `multi-qa-mpnet-base-dot-v1`, chosen for retrieving over `references/`, while the meta corpus is indexed with the general symmetric model `all-mpnet-base-v2` into its own Chroma collection, `meta_docs` in `.chromadb-meta/`[^architecture]. That model choice tracks what each corpus actually contains: the meta corpus has no book sources[^rules-research] and consists of general-purpose prose (docs, rules, agent/skill files describing this repo's own pipeline)[^architecture], which is why it uses a symmetric embedding model rather than the Spark corpus's asymmetric one[^rules-research].

Beyond the embedding model, the two instances share no state at any layer: no registry, no Chroma collection, no content manifest. Each is a fully independent instance of the same pipeline shape (registry question → RAG draft/verify/redraft → section projection → content page → build)[^architecture].

## The append-only registry

`research/questions.yaml` never has an existing record mutated: new questions are added by appending a fresh `pending` record, and existing records keep their `id`, `section`, and `text` forever once written[^rules-registry]. Two scripts enforce this:

- `scripts/add_question.py` mints a new id and appends a `pending` record; it never mutates an existing record[^rules-registry][^architecture].
- `scripts/recompute_question.py` flips one existing record's status to `pending` and backs up its old answer file, but touches no other record or file[^rules-registry][^architecture].

Separately, `scripts/registry.py` loads, saves, and validates `questions.yaml` for the `Registry`/`Section`/`Question` dataclasses[^architecture]. The rules also forbid hand-editing an existing record's `id`, `section`, or `text`; a changed question is added as a new record instead of being rewritten in place[^rules-registry]. Because of this, the rest of the pipeline treats `questions.yaml` as the one-way source of truth: recompute always starts at the registry and flows forward through per-question answers, section projections, and content pages, never the other direction[^architecture].

## Sources

[^architecture]: architecture — references-meta/docs/architecture.md
[^rules-registry]: rules-registry — references-meta/docs/rules/registry.md
[^runbook]: runbook — references-meta/docs/runbook.md
[^agent-meta-draft]: agent-meta-draft — references-meta/agents/meta-section-draft.md
[^skill-answer-question]: skill-answer-question — references-meta/skills/answer-question.md
[^rules-research]: rules-research — references-meta/docs/rules/research.md
