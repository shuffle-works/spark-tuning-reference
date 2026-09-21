"""MCP stdio server exposing the local RAG retrieval as a single tool.

Run:  uv run --group mcp scripts/mcp_server.py

One tool, `ask_spark_docs`, mirrors ask.py's per-question block as structured
data (ranked chunks + citable source_ids). The embedding model (~420 MB) and the
ChromaDB collection are loaded ONCE per corpus and reused across calls — that is
the whole point of a persistent server versus shelling ask.py per question.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

# Allow both `uv run scripts/mcp_server.py` (sibling import) and package import.
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from mcp.server.mcpserver import MCPServer
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "the 'mcp' package is not installed — run with: "
        "uv run --group mcp scripts/mcp_server.py"
    ) from exc

from ask import Chunk, load_model, load_source_urls, open_collection, retrieve
from corpus import CORPORA

mcp = MCPServer("spark-tuning-reference")


@lru_cache(maxsize=None)
def _resources(corpus: str):
    """Load (model, collection, urls) once per corpus; reused across calls."""
    prof = CORPORA[corpus]
    return load_model(prof), open_collection(prof), load_source_urls(prof.index_path)


def _chunk_dict(c: Chunk) -> dict:
    return {
        "rank": c.rank,
        "source_id": c.source_id,
        "version_bucket": c.meta["version_bucket"],
        "relevance": round(c.relevance, 3),
        "local_path": c.meta["local_path"],
        "section_path": c.meta["section_path"],
        "url": c.url,
        "text": c.text,
    }


@mcp.tool()
def ask_spark_docs(
    question: str,
    k: int = 15,
    version: str | None = None,
    corpus: Literal["spark", "meta"] = "spark",
) -> dict:
    """Retrieve the top-k source chunks relevant to a Spark tuning question.

    Returns the ranked chunks (full text + metadata + relevance score) and the
    ordered, deduped `citable_source_ids` — the only source IDs citable for this
    question. `version` (3.0/3.5/4.0/n/a) keeps the matching bucket AND the
    version-agnostic `n/a` bucket. `corpus` selects the Spark docs or the
    meta ("how this site works") corpus.
    """
    model, collection, urls = _resources(corpus)
    result = retrieve(
        [question], corpus=corpus, version=version, k=k,
        model=model, collection=collection, urls=urls,
    )[0]
    return {
        "question": result.question,
        "version_filter": version,
        "chunks": [_chunk_dict(c) for c in result.chunks],
        "citable_source_ids": result.source_ids,
    }


if __name__ == "__main__":
    _resources("spark")  # warm the default corpus at startup, not on first call
    mcp.run()  # stdio transport by default
