---
name: answer-question
description: Answer or recompute one registry question end-to-end — RAG draft, verify, humanize, project the section, first-gen or flag its content page, commit. Use for a single question id from questions.yaml.
disable-model-invocation: true
---

# Answer one question

Input: a question id (e.g. `3.6-q07`). Preconditions: the RAG index exists
(`.chromadb/`), and the id is in `research/questions.yaml`.

## Procedure

1. **Read the record.** `uv run python -c "from scripts.registry import *; q=get_question(load_registry(__import__('pathlib').Path('research/questions.yaml')),'<id>'); print(q.section, q.version, q.k, q.text)"`. Note section-id, version, k (null → section default_k), and text.

2. **Draft** (dispatch `spark-section-draft`): pass section-title, section-id, a one-item question list = the record's text, `k` (record k or section default_k), version (only if not `n/a`), and **output-path** `research/answers/q/<id>.md`.

3. **Verify** (dispatch `spark-section-verify`): same inputs + output-path. Get `{passed, issues[]}`.

4. **Redraft if needed** (dispatch `spark-section-redraft`, at most once) with the issues, then re-verify once. If still failing, the answer keeps its `[NEEDS-REVIEW: ...]` markers — set the record status accordingly in step 7.

5. **Humanize.** Copy `research/answers/q/<id>.md` to a unique scratch path first (per `docs/rules/research.md` #8). Dispatch the `writing-prose-like-a-human-for-agents:prose-humanizer` agent on `research/answers/q/<id>.md`, with the same hard constraints used elsewhere: never touch `[^id]` footnotes, the `## Sources` block, `[UNRESOURCED]`/`[NEEDS-REVIEW]` markers, config names/numbers/version strings, or the `## <question>` heading. Then run the deterministic backstop, `scripts/check_prose.py` (`docs/rules/editorial.md` #2):
   - `uv run python -m scripts.check_prose --diff <scratch-copy> research/answers/q/<id>.md` — fails if the humanizer touched a protected element.
   - `uv run python -m scripts.check_prose research/answers/q/<id>.md` — flags leftover AI-tell vocabulary/structure.
   If either fails, re-dispatch the humanizer once with the reported issues, then re-run both checks; if still failing, leave the issues and note them in the final status. This is the artifact the build ultimately reads (via the projection) — this closes backlog C8.

6. **Project the section:** `uv run python -m scripts.project_section <section-id>`.

7. **Update the record status** in `questions.yaml`: `answered` if verify passed and no markers remain, else `needs-review`. (Edit the one record's `status:` line.)

8. **Content state:** `uv run python -m scripts.content_state`. For each page fed by this section:
   - **ungenerated** → generate it: read the page's `brief:` and `assembled_from:` from `content/manifest.yaml`, write `content/<...>.md` from the projection per the brief (follow `docs/rules/content.md` for the frozen anchor and fenced-code-in-blockquote rules), humanize it the same way as step 5 (scratch copy, dispatch `writing-prose-like-a-human-for-agents:prose-humanizer`, then `scripts/check_prose.py` lint + `--diff` against the scratch copy), then `uv run python -m scripts.content_state --accept <page>`.
   - **stale** → do NOT edit the page. Leave it flagged (the build will warn). Report it to the user for manual editing.

9. **Check + commit:** `uv run scripts/prebuild_checks.py --corpus spark` and `uv run scripts/smoke_content.py` (spot-check both succeed), then commit only the touched files:
   `git add research/questions.yaml research/answers/q/<id>.md research/answers/<section-id>.md content/ research/content-state.yaml`
   `git commit -m "docs: answer <id> with citations"`
   (Drop paths that weren't touched. If a stale page was left unedited, say so in the final status.)

## Batch mode

To answer all pending questions: `uv run python -m scripts.list_pending` then run this procedure per id (a `Workflow` may pipeline them; concurrency is per-question). The per-process model-load reason for a concurrency cap no longer applies now that retrieval goes through the warm `ask_spark_docs` MCP server; leave any cap to the operator's judgment.
