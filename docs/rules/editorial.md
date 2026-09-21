# Editorial rules

Prose rules for the Spark Tuning Reference, enforced by the Draft/Verify/Redraft
agents (`.claude/agents/spark-section-*.md`) that make up the Step 4 answering pipeline
(see `docs/architecture.md`). Every writer or verifier agent touching `content/*.md` or
`research/answers/**` must follow this file. Add new rules here. Don't copy-paste them
into individual agent files; the agents reference this file so it stays the single source.

These rules apply equally to the `meta-section-*` agents and
`content/meta/**`/`research/meta/answers/**` (see `docs/architecture.md`'s
Corpora section). Rule 2's example (`leverage broadcast joins`) is a Spark-corpus
illustration only.

## Rules

1. Never editorialize about source coverage ("the cited sources don't document X",
   "don't name", "don't cover", "don't specify", "don't address", "don't mention", or
   equivalent). Added 2026-07-16. It reads as complaining about the sources rather than
   stating what's known. The reference asserts what's supported and stops; it doesn't
   narrate the gap. If a claim lacks support, mark it `[UNRESOURCED]` per the gap
   convention in `docs/rules/research.md`, or drop the claim. Never add a sentence
   describing what the sources fail to say.
   - Bad: "The cited sources don't document what happens when `minExecutors` is set
     higher than `maxExecutors`."
   - Good: `[UNRESOURCED]`-mark the specific claim, or omit it.

2. Prose style is applied by the `writing-prose-like-a-human-for-agents:prose-humanizer`
   agent (Humanize stage, `.claude/skills/answer-question/SKILL.md` step 5/8), not by the
   Draft/Verify/Redraft agents. `scripts/check_prose.py` is its deterministic, no-LLM
   backstop. Run it after every Humanize dispatch:
   - `check_prose.py <file>` lints leftover AI-tell vocabulary (significance inflation,
     inflated verbs, structural tics like "In summary"/"Additionally,", vague
     attribution), bans curly quotes, and caps em dashes at 0.
   - `check_prose.py --diff <before> <after>` checks the humanizer didn't touch a
     protected element: `[^id]` footnotes, the `## Sources` block,
     `[UNRESOURCED]`/`[NEEDS-REVIEW]` markers, the `## <question>` heading, or any
     numeric/config token.

   The vocabulary/structural list is a literal blocklist, with no semantic understanding
   behind it. It will false-positive on legitimate technical usage in this Spark-focused
   corpus (e.g. `leverage broadcast joins`). A lint failure is a signal to re-dispatch the
   humanizer once. It isn't an automatic hard block.
