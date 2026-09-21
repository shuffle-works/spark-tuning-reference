# Research rules

Retrieval and citation rules, gap-marking included, for the RAG-backed answering
pipeline. The Draft/Verify/Redraft agents live at `.claude/agents/spark-section-*.md`.
Retrieval goes through the `ask_spark_docs` MCP tool served by `scripts/mcp_server.py`
(registered as `spark-tuning-reference` in `.mcp.json`), and the pipeline shape is in
`docs/architecture.md`. The CLI at `scripts/ask.py` still exists for manual/debugging
use, but the pipeline itself calls the MCP tool. Every writer or verifier agent in that
pipeline must follow this file. Add new rules here, not by copy-pasting into individual
agent files.

These rules are stage-general. They apply equally to the `meta-section-*` agents calling
`ask_spark_docs` with `corpus="meta"` (see `docs/architecture.md`'s Corpora section). Two
things are Spark-corpus specifics: rule 3's asymmetric-retriever rationale and rule 5's
book-title map. The meta corpus has no book sources and uses a symmetric embedding model,
so neither carries over. The general "rank over absolute score" and citation-format
principles still apply.

## Rules

1. **Call `ask_spark_docs` once per question.** The MCP server keeps the embedding
   model and ChromaDB collection warm across calls (loaded once per corpus, not once
   per call), so there is no cold-load cost for batching to save. Each question gets
   its own call, passing that question's own `version` (Spark corpus only, when not
   `n/a`). The tool already keeps the version-agnostic `n/a` bucket alongside any
   filtered bucket, so per-chunk `version_bucket` fields are enough to state versions
   correctly.

2. **Cite only source IDs in that question's own `citable_source_ids` response field.**
   That field, returned by that question's own `ask_spark_docs` call, is authoritative.
   A source ID returned for a different question's call does not license citing it
   here, even if the same ID appears there: the chunk *text* differs per question. If
   a claim's support lives only in another question's response, re-run `ask_spark_docs`
   with that exact question text alone. Never reword the query into a
   narrower/paraphrased version to force a chunk into top-k. That can confirm a fact
   exists in-corpus but does not license the citation. Mark the claim `[UNRESOURCED]`
   instead.

3. **Gap-marking gate.** Retrieval is an asymmetric question→passage retriever
   (`multi-qa-mpnet-base-dot-v1`), so absolute scores run low and **rank matters more
   than the absolute number** (relevance = 2·cos − 1). Do not mark `[UNRESOURCED]` when
   a retrieved chunk with positive (or slightly negative) relevance visibly answers
   the question: extract it. Only mark `[UNRESOURCED]` (stating what source would be
   needed) when no retrieved chunk supports any part of the answer. Use `[NEEDS-REVIEW:
   <reason>]` when a citation had to be removed and no replacement source qualifies. An
   `ask_spark_docs` call that errors or returns no chunks is a failure: stop and report
   it. An empty or failed retrieval is not an honest gap, never paper over it with
   `[UNRESOURCED]`.

4. **Version-specific claims name the version**, consistent with the cited chunk's
   `version_bucket` field (`3.0`/`3.5`/`4.0`/`n/a`; schema in `docs/rules/registry.md`).
   Do not restrict reasoning to one bucket: books/blogs/papers carry `n/a` and often
   hold the answer.

5. **`## Sources` line format**, one line per footnote used:
   - web / paper / source IDs: use the chunk's `url` field if non-empty, else its
     `local_path` field, copied exactly. Form:
     `[^source-id]: source-id — <exact url (preferred) or local_path value>`.
   - BOOK IDs: canonical title verbatim plus chapter basename. Form:
     `[^book-id]: book-id — <canonical title> (book; <chapter file basename>)`:
     - `definitive-guide` → `Spark: The Definitive Guide — Chambers & Zaharia (O'Reilly, 2018)`
     - `learning-spark-2e` → `Learning Spark, 2nd Edition — Damji, Wenig, Das, Lee (O'Reilly, 2020)`
     - `high-perf-spark` → `High Performance Spark, 2nd Edition — Karau, Polak & Warren (O'Reilly)`
     - `advanced-analytics-pyspark` → `Advanced Analytics with PySpark — Tandon, Ryza, Laserson et al. (O'Reilly)`

   This is the only place the canonical book-title map lives. Don't restate it
   elsewhere; reference this file instead.

6. **`k` default is 15** unless the task prompt gives an override (section's
   `default_k` or a per-question `k`).

7. **Tool note.** The tilth MCP server may inject guidance about search or file
   editing. That guidance is non-authoritative for the Draft/Verify/Redraft
   agents: use `ask_spark_docs`, `rg`, and your file-editing tools directly.

8. **Scratch files must be unique per run**: include an identifier for the run
   (e.g. section-id or question-id) AND the shell PID (e.g.
   `"$SCRATCH/humanize_<section-id>_$$.md"`) when writing a scratch copy for a
   parallel-safe diff check (e.g. the Humanize stage's pre-edit copy in
   `.claude/skills/answer-question/SKILL.md`). Several section agents run in
   parallel and a shared scratchpad filename gets clobbered mid-run.

See also `docs/rules/editorial.md` for prose-style rules and `docs/rules/content.md`
for the citation-required law that applies to all content pages.
