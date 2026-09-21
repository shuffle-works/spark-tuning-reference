# Agents & Orchestration

## Draft, Verify, and Redraft

The pipeline splits judgment-requiring work (retrieval, drafting, verifying citations, fixing issues, humanizing prose) into separate agents rather than folding it into deterministic scripts, because that work has no single correct output given its inputs[^architecture]. For the meta corpus these are `meta-section-draft`, `meta-section-verify`, and `meta-section-redraft`, mirrors of the Spark corpus's `spark-section-draft`/`spark-section-verify`/`spark-section-redraft`, adapted to the meta corpus's paths and `--corpus meta` invocations but not sharing prompt text with them[^architecture].

**Draft** produces one citation-backed answer per question from the local RAG index. It writes the finished answer using an `## <question text>` heading with prose beneath, footnotes every factual claim with the source ID `ask.py` printed, and closes with a `## Sources` section[^agent-spark-draft]. For the meta corpus this same agent role is described as drafting one section of the meta-doc "one citation-backed answer per question," acting as the Draft stage of the meta answering pipeline[^agent-meta-draft].

**Verify** checks a drafted section: it validates gaps, checks every cited claim against its underlying chunk, and checks that the `## Sources` block is formatted correctly[^agent-meta-verify].

**Redraft** is dispatched only if Verify reports issues, and only once, taking those issues as input; after it runs, the section is re-verified a single time. If it still fails after that one redraft-and-re-verify cycle, the answer keeps whatever `[NEEDS-REVIEW: ...]` markers remain, and the question's registry record is set to `needs-review` rather than `answered`[^skill-answer-meta-question].

The `answer-meta-question` skill runs these stages in a fixed sequence for a single question: read the registry record, dispatch Draft, dispatch Verify, dispatch Redraft-if-needed followed by one re-verify, then Humanize, project the section, update the record status, refresh content state, and finally build and commit[^skill-answer-meta-question]. This order (Draft → Verify → an optional Redraft-then-re-Verify loop → Humanize → downstream projection and build steps → commit) is the same sequence the answering pipeline documents for orchestrating one question end to end[^architecture].

## Why citations are scoped per question

The verify agent's citation check requires two things for every footnoted claim: the source ID must appear on THAT question's own `citable source_ids` line, and the chunk excerpt under that question must actually support the claim. A footnote whose source ID is not on that question's `citable source_ids` line is a FAIL even if the underlying fact is true. The claim-support check against that question's own chunk text is the real gate, not the mere existence of the ID somewhere in the corpus[^agent-spark-verify][^agent-meta-verify].

The reason the same ID can't cross questions is that retrieval is per-question: a source ID retrieved under a different question's block does not license citing it here, because the chunk *text* returned for that ID differs per question[^rules-research]. The Draft stage states the same constraint from the writer's side: answer each question from its own retrieval block only, since a source can be retrieved for several questions but with different chunks, and a fact seen under one question's chunks does not license citing that source under another question unless that question's own chunk text states it. The held-out gate that motivated this rule caught exactly this failure: a true `peakExecutionMemory` definition retrieved under one question was cited under a different question whose own chunks only held an executor-level table[^agent-spark-draft].

This is why Redraft treats a "misattributed footnote" (source ID not on that question's `citable source_ids` line) as something to fix rather than wave through: either re-cite to a source ID that is on that question's line and supports the claim, or mark the claim `[NEEDS-REVIEW: <reason>]` and remove the wrong footnote, never leaving an orphan footnote[^agent-meta-redraft][^agent-spark-redraft].

## Humanize and its deterministic backstop

The Humanize stage applies prose style to a drafted answer. It is a separate step run by the `writing-prose-like-a-human-for-agents:prose-humanizer` agent (an installed plugin), not by the Draft/Verify/Redraft agents themselves[^rules-editorial][^architecture]. In the per-question skill flow it sits as step 5 of 8, after Draft, Verify, and any Redraft/re-Verify cycle, and before `check_prose`, `project_section`, and `content_state`[^architecture][^rules-editorial]. For the meta corpus specifically, the humanizer runs against `research/meta/answers/q/<id>.md` (copied first to a unique scratch path) under hard constraints: it must never touch `[^id]` footnotes, the `## Sources` block, `[UNRESOURCED]`/`[NEEDS-REVIEW]` markers, or the `## <question>` heading[^skill-answer-meta-question].

The deterministic backstop is `scripts/check_prose.py`, described as a "no-LLM lint/backstop" for the Humanize stage[^architecture]. It runs in two forms after every humanize pass. Plain `check_prose.py <file>` lints the humanized file for leftover AI-tell vocabulary (significance inflation, inflated verbs, structural tics such as conclusion phrases or additive transitions, vague attribution), bans curly quotes, and caps em dashes at zero[^rules-editorial][^architecture]. `check_prose.py --diff <before> <after>` instead checks that the humanizer didn't touch a protected element: `[^id]` footnotes, the `## Sources` block, `[UNRESOURCED]`/`[NEEDS-REVIEW]` markers, the `## <question>` heading, or any numeric/config token[^rules-editorial][^architecture]. For the meta pipeline, both invocations run as `uv run python -m scripts.check_prose --diff <scratch-copy> research/meta/answers/q/<id>.md` and `uv run python -m scripts.check_prose research/meta/answers/q/<id>.md`[^skill-answer-meta-question].

The vocabulary/structural list check_prose applies is a literal blocklist rather than semantic understanding, so it can false-positive on legitimate technical usage (the rule's own example is a Spark phrase about broadcast joins that trips the blocklist even though it is idiomatic)[^rules-editorial]. A lint failure is treated as a signal to re-dispatch the humanizer once rather than an automatic hard block[^rules-editorial]; in the meta procedure, if either check fails the humanizer is re-dispatched once with the reported issues and both checks re-run, and if still failing the issues are left in place and noted in the final status[^skill-answer-meta-question].

## Sources

[^architecture]: architecture — references-meta/docs/architecture.md
[^agent-spark-draft]: agent-spark-draft — references-meta/agents/spark-section-draft.md
[^agent-meta-draft]: agent-meta-draft — references-meta/agents/meta-section-draft.md
[^agent-meta-verify]: agent-meta-verify — references-meta/agents/meta-section-verify.md
[^skill-answer-meta-question]: skill-answer-meta-question — references-meta/skills/answer-meta-question.md
[^agent-spark-verify]: agent-spark-verify — references-meta/agents/spark-section-verify.md
[^rules-research]: rules-research — references-meta/docs/rules/research.md
[^agent-meta-redraft]: agent-meta-redraft — references-meta/agents/meta-section-redraft.md
[^agent-spark-redraft]: agent-spark-redraft — references-meta/agents/spark-section-redraft.md
[^rules-editorial]: rules-editorial — references-meta/docs/rules/editorial.md
