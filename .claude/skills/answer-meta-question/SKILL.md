---
name: answer-meta-question
description: Answer or recompute one question from the meta-doc registry (research/meta/questions.yaml) end-to-end — RAG draft, verify, humanize, project the section, first-gen or flag its content page, commit. Use for a single question id from the meta corpus.
disable-model-invocation: true
---

# Answer one meta-doc question

Input: a question id (e.g. `M2-q03`). Preconditions: the meta RAG index exists (`.chromadb-meta/`, built via `uv run scripts/build_index.py --corpus meta`), and the id is in `research/meta/questions.yaml`.

## Procedure

1. **Read the record.** `uv run python -c "from scripts.registry import *; q=get_question(load_registry(__import__('pathlib').Path('research/meta/questions.yaml')),'<id>'); print(q.section, q.k, q.text)"`. Note section-id, k (null → section default_k), and text. (The meta corpus has no version concept — every question is `n/a`.)

2. **Draft** (dispatch `meta-section-draft`): pass section-title, section-id, a one-item question list = the record's text, `k` (record k or section default_k), and **output-path** `research/meta/answers/q/<id>.md`.

3. **Verify** (dispatch `meta-section-verify`): same inputs + output-path. Get `{passed, issues[]}`.

4. **Redraft if needed** (dispatch `meta-section-redraft`, at most once) with the issues, then re-verify once. If still failing, the answer keeps its `[NEEDS-REVIEW: ...]` markers — set the record status accordingly in step 7.

5. **Humanize.** Copy `research/meta/answers/q/<id>.md` to a unique scratch path first (per `docs/rules/research.md` #8). Dispatch the `writing-prose-like-a-human-for-agents:prose-humanizer` agent on `research/meta/answers/q/<id>.md`, with the same hard constraints used for the Spark pipeline: never touch `[^id]` footnotes, the `## Sources` block, `[UNRESOURCED]`/`[NEEDS-REVIEW]` markers, or the `## <question>` heading. Then run the deterministic backstop:
   - `uv run python -m scripts.check_prose --diff <scratch-copy> research/meta/answers/q/<id>.md`
   - `uv run python -m scripts.check_prose research/meta/answers/q/<id>.md`
   If either fails, re-dispatch the humanizer once with the reported issues, then re-run both checks; if still failing, leave the issues and note them in the final status.

6. **Project the section:** `uv run python -m scripts.project_section <section-id> --corpus meta`.

7. **Update the record status** in `research/meta/questions.yaml`: `answered` if verify passed and no markers remain, else `needs-review`.

8. **Content state:** `uv run python -m scripts.content_state --corpus meta`. For each page fed by this section:
   - If the section has **no manifest entry yet** in `content/meta/manifest.yaml` (the meta manifest starts as `groups: []` and grows only as sections finish — unlike the Spark corpus's manifest, which was fully populated up front): confirm every question in the section is `answered`/`needs-review` (i.e. `project_section` above succeeded for the whole section, not just this one question), then add a manifest entry (`file`, `anchor`, `title`, `assembled_from: research/meta/answers/<section-id>.md`, `brief`) before generating the page.
   - **ungenerated** → generate it: read the page's `brief:` and `assembled_from:` from `content/meta/manifest.yaml`, write `content/meta/<...>.md` from the projection (follow `docs/rules/content.md` for the fenced-code-in-blockquote rule; the frozen-anchor cross-repo contract in that file's rule 3 does NOT apply here — `content/meta/manifest.yaml` anchors are free to change), then humanize it the same way as step 5, then `uv run python -m scripts.content_state --corpus meta --accept <page>`.
   - **stale** → do NOT edit the page. Leave it flagged (the build will warn). Report it to the user for manual editing.

9. **Check + commit:** `uv run scripts/prebuild_checks.py --corpus meta` and `uv run scripts/smoke_content.py` (spot-check both succeed), then commit only the touched files:
   `git add research/meta/questions.yaml research/meta/answers/q/<id>.md research/meta/answers/<section-id>.md content/meta/ research/meta/content-state.yaml`
   `git commit -m "docs: answer <id> with citations (meta-doc)"`
   (Drop paths that weren't touched. If a stale page was left unedited, say so in the final status.)

## Batch mode

To answer all pending meta questions: `uv run python -m scripts.list_pending --corpus meta` then run this procedure per id. The per-process model-load reason for a concurrency cap no longer applies now that retrieval goes through the warm `ask_spark_docs` MCP server; leave any cap to the operator's judgment.
