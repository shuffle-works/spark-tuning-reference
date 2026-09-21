# Runbook

Operator procedures for the question-granular answering pipeline. Background
and data model: `docs/architecture.md`.

## Add a question

```
uv run python -m scripts.add_question "<text>" --section <id> [--version X] [--k N]
```

Appends a `pending` record to `research/questions.yaml` and prints the new
id (never mutates existing records). `--version` is one of `3.0`/`3.5`/`4.0`/
`n/a` (default `n/a`); `--k` overrides the section's `default_k` for this
question only.

Then run the `answer-question` skill with the printed id. For the meta-doc
corpus, add `--corpus meta` and run the `answer-meta-question` skill
instead.

## Recompute a question

```
uv run python -m scripts.recompute_question <id>
```

Flips that record to `pending` and backs up its old answer file
(`answers/q/<id>.md` → `.md.bak`). Touches no other record or file.

Then run the `answer-question` skill with that id. For the meta-doc corpus,
add `--corpus meta` and run `answer-meta-question` instead.

## Batch: answer all pending questions

```
uv run python -m scripts.list_pending
```

Prints every id with `status: pending`, one per line. Run the `answer-question`
skill for each id (cap concurrent runs at ~4: each shells `ask.py`, which
loads a ~420 MB embedding model). For the meta-doc corpus, add `--corpus meta`
and run `answer-meta-question` for each id instead.

## Accept a stale content page after editing

```
uv run python -m scripts.content_state --accept <page>
```

Use after hand-editing a page the pipeline flagged **stale**, so its recorded
hash matches the current section projection again. `<page>` is the manifest
`file:` path, e.g. `content/bottlenecks/skew.md`. For the meta-doc corpus, add
`--corpus meta` (`<page>` is then a `content/meta/...` path).

## Checking content before it ships

```
uv run scripts/prebuild_checks.py --corpus spark
```

Runs the manifest-mapping gate (fatal) then the staleness report (advisory)
for a corpus; CI runs this for both `spark` and `meta` (`.github/workflows/ci.yml`).
It reports each content page as `ungenerated`, `stale`, or up to date:

- `ungenerated`: no recorded hash yet; the page has never been generated
  from its section projection.
- `stale`: the section's answers changed since this page was generated or
  last accepted; the page needs a manual edit, then
  `content_state --accept <page>`.

The warning is non-fatal, but a stale/ungenerated page means its prose may not
reflect the latest answers. `uv run scripts/smoke_content.py` separately checks
anchor coverage, footnote resolution, and blockquote-fence safety directly
against `content/*.md`; `uv run scripts/content_state.py --check` is the hard
CI gate on staleness. This repo does not render HTML: rendering `content/*.md`
happens upstream (`docs/architecture.md`'s "HTML generation" section). After
changing `content/manifest.yaml`, also regenerate the published anchor
contract:

```
uv run scripts/build_anchors.py
```

## Add or regenerate a diagram

Content pages embed diagrams as SVGs compiled from Mermaid sources under
`content/diagrams/`. Each `<name>.mmd` renders to two committed files:
`<name>.svg` (light) and `<name>.dark.svg` (dark).

To add one: write `content/diagrams/<name>.mmd` (a `flowchart`/`stateDiagram-v2`,
structure and labels only, no colour or style directives), then link both SVGs as
a light-only/dark-only `<img>` pair so the upstream renderer's theme toggle picks
the right one:

```
<img class="light-only" src="diagrams/<name>.svg" alt="One plain sentence describing the diagram.">
<img class="dark-only" src="diagrams/<name>.dark.svg" alt="One plain sentence describing the diagram.">
```

Use `diagrams/…` from a top-level page and `../diagrams/…` from a
`content/bottlenecks/` page. Regenerate the SVGs after any `.mmd` change:

```
uv run scripts/render_diagrams.py
```

The renderer uses `mermaidx` (real mermaid.js inside an embedded JS engine, no
Node, no browser); the dependency is declared inline (PEP 723) and provisioned by
`uv` only for that run. The palette lives in the script, applied to both themes,
so `.mmd` sources stay colour-free. `mermaidx` approximates text width, so eyeball
new diagrams and add explicit `<br/>` breaks (or rely on the script's
`wrappingWidth`) if a long token wraps mid-word.

Two things are the consumer's job, not this repo's: the upstream renderer
(`sparkforensics`) must serve the `content/diagrams/` asset files (its vendor step
copies only `.md` today), and a linked SVG follows the viewer's OS colour scheme,
not the site's manual light/dark toggle.

## Serve retrieval over MCP (Claude tool)

`scripts/mcp_server.py` exposes the same retrieval as `ask.py` as one MCP stdio
tool, `ask_spark_docs(question, k=15, version=None, corpus="spark")`. Unlike the
CLI (which reloads the ~420 MB embedding model on every invocation), the server
loads the model and opens the ChromaDB collection **once at startup** and reuses
them across calls: warm the default `spark` corpus at boot, lazily load `meta`
on first use.

Register it with Claude (`.mcp.json`, or `claude mcp add`):

```json
{
  "mcpServers": {
    "spark-tuning-reference": {
      "command": "uv",
      "args": ["run", "--directory", "${CLAUDE_PROJECT_DIR:-.}", "--group", "mcp", "scripts/mcp_server.py"]
    }
  }
}
```

The `mcp` dependency group is not part of the default or `dev` install; it pulls
in the `mcp` SDK plus the full `research` retrieval runtime (`chromadb`,
`sentence-transformers`, `trafilatura`, `tiktoken`, `rich`).
Requires a built index (`scripts/build_index.py`) for the corpus being queried.

## Maintaining the meta corpus's reference symlinks

`references-meta/` holds symlinks into the real project files it indexes
(`docs/**/*.md`, `CLAUDE.md`, `.claude/skills/**/*.md`,
`.claude/agents/**/*.md`), never copies. To add a new file to the meta
corpus: create the symlink under `references-meta/` pointing at the real
file, add a matching entry (`id`, `type: doc`, `local:`) to
`references-meta/index.yaml`, then rerun
`uv run scripts/build_index.py --corpus meta` to rebuild `.chromadb-meta/`.

## Header/footer/sidebar shell, retired here

This repo used to carry the HTML shell (`landing.html`, `site/templates/chapter-shell.mjs`)
that `shuffle-works/shuffle-works.github.io` publish-time-injected a shared
product bar and footer into, matching exact strings and selectors, plus a
sidebar-dedup style (`tests/product_bar_contract.test.mjs` guarded it). That shell no
longer exists here: HTML rendering moved upstream (`docs/architecture.md`'s
"HTML generation" section), so the product-bar contract now lives against
whichever repo emits the markup the hub injects into. This repo carries no
markup at all, and so can't break that contract by itself anymore.
