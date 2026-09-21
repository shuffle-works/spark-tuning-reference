"""Query the local ChromaDB index for chunks relevant to research questions.

Usage: uv run scripts/ask.py [--version 3.5] [--k 15] "question one" ["question two" ...]

Pass every question for a section in ONE invocation — the embedding model (~420 MB)
loads once per process, so batching all of a section's questions here collapses N
cold model loads into 1. Run after build_index.py.

Retrieval notes:
- Embeddings come from multi-qa-mpnet-base-dot-v1 (an asymmetric question->passage
  retriever) with normalize_embeddings=True, and the ChromaDB collection uses the
  default squared-L2 space. On unit vectors L2^2 = 2(1-cos), so the printed relevance
  (1 - distance) equals 2*cos - 1. Rank matters more than the absolute score here:
  read the top chunks; a chunk that visibly answers the question is a real hit even at
  a slightly negative relevance.
- Full chunk text is printed (not a snippet) so a drafter/verifier can extract and
  ground claims from exactly what was retrieved.
- Each question's block is wrapped in `===== QUESTION i/N =====` / `===== END ... =====`
  markers and closes with a `citable source_ids (...)` line listing, in rank order, the
  ONLY source IDs that may be cited for that question — so batched output can't bleed a
  source from one question into another's citations.
- --version keeps the matching bucket AND the version-agnostic `n/a` bucket (books,
  blogs, papers), so a version filter never silently drops version-agnostic answers.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# corpus profiles: importable both as a sibling module (`uv run scripts/ask.py`)
# and as a package member (`from scripts.ask import ...` under pytest).
try:
    from scripts.corpus import CORPORA, Corpus
except ModuleNotFoundError:  # pragma: no cover - direct-script invocation path
    from corpus import CORPORA, Corpus

# Heavy deps (chromadb, sentence_transformers, rich) are imported lazily inside
# the functions that need them so that `from scripts.ask import retrieve` works in
# a minimal test env where the `research` group isn't installed.

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_K = 15  # raised from 10 (2026-07-10): the k=10 gate was stricter than the
# asymmetric retriever reliably delivers for large multi-topic sources (SPIP pages,
# spark-configuration), causing unwinnable redraft loops on true content. See §3.6.
VERSION_BUCKETS = ("3.0", "3.5", "4.0", "n/a")


@dataclass
class Chunk:
    """One ranked retrieval hit: full chunk text plus its metadata and score."""

    rank: int
    source_id: str
    text: str
    meta: dict
    relevance: float  # 1 - distance; see module docstring on the L2/cos relation
    url: str


@dataclass
class QuestionResult:
    """A question, its ranked chunks, and the deduped citable source_ids."""

    question: str
    chunks: list[Chunk]
    source_ids: list[str]  # dedup in rank order — the ONLY IDs citable here


def load_model(corpus: Corpus):
    """Load the corpus's embedding model (the ~420 MB cost)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(corpus.embedding_model)


def open_collection(corpus: Corpus):
    """Open the corpus's persistent ChromaDB collection."""
    import chromadb

    client = chromadb.PersistentClient(path=str(corpus.chroma_path))
    return client.get_collection(corpus.collection_name)


def retrieve(
    questions: list[str],
    *,
    corpus: str = "spark",
    version: str | None = None,
    k: int = DEFAULT_K,
    model=None,
    collection=None,
    urls: dict[str, str] | None = None,
) -> list[QuestionResult]:
    """Rank-retrieve chunks for each question. Side-effect-free (no printing).

    `model`, `collection`, and `urls` may be injected — a persistent process
    (the MCP server) loads the model/collection ONCE and reuses them across
    calls; the CLI injects the ones it already opened for error handling. When
    omitted they are loaded from the named corpus profile. Keeps the
    version-bucket (`[version, "n/a"]`) filter and citable-source dedup.
    """
    prof = CORPORA[corpus]
    if model is None:
        model = load_model(prof)
    if collection is None:
        collection = open_collection(prof)
    if urls is None:
        urls = load_source_urls(prof.index_path)

    embeddings = model.encode(questions, normalize_embeddings=True).tolist()
    where = {"version_bucket": {"$in": [version, "n/a"]}} if version else None

    results: list[QuestionResult] = []
    for question, embedding in zip(questions, embeddings):
        res = collection.query(query_embeddings=[embedding], n_results=k, where=where)
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        distances = res["distances"][0]

        chunks: list[Chunk] = []
        seen: list[str] = []
        for rank, (doc, meta, distance) in enumerate(zip(docs, metas, distances), start=1):
            source_id = meta["source_id"]
            chunks.append(
                Chunk(
                    rank=rank,
                    source_id=source_id,
                    text=doc,
                    meta=meta,
                    relevance=1 - distance,
                    url=urls.get(source_id, "n/a"),
                )
            )
            if source_id not in seen:
                seen.append(source_id)
        results.append(QuestionResult(question=question, chunks=chunks, source_ids=seen))
    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query the RAG index for source chunks.")
    parser.add_argument("questions", nargs="+", help="one or more research questions (batched in one model load)")
    parser.add_argument("--version", choices=VERSION_BUCKETS, help="restrict to this bucket plus the n/a bucket")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help=f"top-k chunks per question (default {DEFAULT_K})")
    parser.add_argument("--corpus", choices=list(CORPORA), default="spark", help="which RAG corpus to query")
    return parser.parse_args(argv)


def load_source_urls(index_path: Path) -> dict[str, str]:
    """source_id -> url, for the page/URL line (books have no url)."""
    index = yaml.safe_load(index_path.read_text())
    return {source["id"]: source.get("url") or "n/a" for source in index["sources"]}


def format_result(chunk: Chunk) -> str:
    meta = chunk.meta
    body = chunk.text.strip()
    indented = "\n".join(f"        {line}" for line in body.splitlines())
    lines = [
        f"[{chunk.rank}] {meta['source_id']}  (version: {meta['version_bucket']}, relevance: {chunk.relevance:.3f})",
        f"    file: {meta['local_path']}",
        f"    section: {meta['section_path']}",
        f"    url: {chunk.url}",
        "    chunk:",
        indented,
    ]
    return "\n".join(lines)


def main() -> int:
    from rich.console import Console

    console = Console()
    args = parse_args(sys.argv[1:])
    corpus = CORPORA[args.corpus]

    if not corpus.chroma_path.exists():
        console.print(
            f"[red]error[/red] no index at {corpus.chroma_path} — "
            f"run scripts/build_index.py --corpus {args.corpus} first"
        )
        return 1

    # Open the collection here (not inside retrieve) to keep the CLI's specific
    # "could not open collection" error message and exit code.
    try:
        collection = open_collection(corpus)
    except Exception as exc:
        console.print(f"[red]error[/red] could not open collection '{corpus.collection_name}': {exc}")
        return 1

    model = load_model(corpus)
    results = retrieve(
        args.questions,
        corpus=args.corpus,
        version=args.version,
        k=args.k,
        model=model,
        collection=collection,
    )

    total = len(results)
    for qi, result in enumerate(results, start=1):
        # Explicit, machine-parseable per-question header so a batched call's blocks are
        # never confused for one another when a drafter/verifier reads the combined output.
        console.print(f"===== QUESTION {qi}/{total} =====")
        console.print(f"[bold]question:[/bold] {result.question}")
        if args.version:
            console.print(f"version filter: {args.version} (+ n/a)")
        console.print()

        if not result.chunks:
            console.print("[yellow]no chunks found[/yellow] (try omitting --version for cross-bucket retrieval)")
        else:
            for chunk in result.chunks:
                console.print(format_result(chunk))
                console.print()

        # Dedup source IDs in rank order — the ONLY IDs citable for THIS question. A
        # drafter/verifier reads this line instead of re-scanning the chunk blocks, so a
        # source from another question's block can't leak into this one's citations.
        ids = ", ".join(result.source_ids) or "(none)"
        console.print(f"citable source_ids (question {qi}/{total}, rank order): {ids}")

        console.print(f"===== END QUESTION {qi}/{total} =====")
        console.print("─" * 80)
        console.print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
