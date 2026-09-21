# Registry rules

Rules for `research/questions.yaml`, the single source of truth for the answering
pipeline (data model: `docs/architecture.md`; operator commands: `docs/runbook.md`).
They apply per registry instance. `research/questions.yaml` (spark corpus) and
`research/meta/questions.yaml` (meta corpus) are independent: an id need not be
unique across the two.

## Rules

1. **Append-only.** `scripts/add_question.py` mints an id and appends a `pending`
   record. It never mutates an existing record. `scripts/recompute_question.py` flips
   one record to `pending` and backs up its old answer file, touching no other record
   or file. Never hand-edit an existing record's `id`, `section`, or `text`; add a new
   question instead.

2. **`questions[].id` is stable.** Never renumbered or reused, even if a question is
   later reworded or dropped.

3. **`questions[].version` is one of `3.0` / `3.5` / `4.0` / `n/a`**, passed to
   `ask.py --version`. See `docs/rules/research.md` for how the answering pipeline
   reasons about version buckets during retrieval.

4. **The registry's header comment does not survive a CLI write.**
   `scripts/registry.py`'s `save_registry()` uses `yaml.safe_dump`, which drops
   comments, so `add_question`/`recompute_question` regenerate the file without it. The
   comment is a documentation aid on the committed snapshot only (not read by any
   script); re-add it by hand after such an edit if you want it to persist.

5. **Never edit a downstream artifact as if it were the source of truth.** Per-question
   answers, section projections, and content pages are all derived, regenerable from
   this registry. Recompute always starts at `questions.yaml` and flows forward (see
   `docs/architecture.md`'s derive-direction diagram).
