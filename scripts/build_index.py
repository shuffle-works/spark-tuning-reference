"""Chunk references/, embed, and persist to the local ChromaDB index.

Usage: uv run scripts/build_index.py
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

import chromadb
import tiktoken
import yaml
from rich.console import Console
from sentence_transformers import SentenceTransformer

from corpus import CORPORA

REPO_ROOT = Path(__file__).resolve().parent.parent

MAX_CHUNK_TOKENS = 1024
MERGE_BELOW_TOKENS = 128
WINDOW_TOKENS = 512
WINDOW_OVERLAP = 64

SCALADOC_OPEN = "/**"

MD_HEADER_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})", re.MULTILINE)
SCALA_DEF_RE = re.compile(
    r"^( {0,4})(?:(?:private|protected|final|override|sealed|abstract|implicit)\s+)*"
    r"(def|class|trait|object|case class)\s+([A-Za-z_][A-Za-z0-9_]*)"
)

console = Console()
encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(encoding.encode(text))


def token_windows(text: str, window: int = WINDOW_TOKENS, overlap: int = WINDOW_OVERLAP) -> list[str]:
    """Split text into overlapping token windows."""
    tokens = encoding.encode(text)
    if not tokens:
        return []
    step = window - overlap
    windows = []
    i = 0
    while True:
        piece = tokens[i : i + window]
        windows.append(encoding.decode(piece))
        if i + window >= len(tokens):
            break
        i += step
    return windows


def chunk_by_tokens(text: str, section_path: str) -> list[tuple[str, str]]:
    """Fixed-window token chunking for .txt sources (papers, plain-text books)."""
    return [(section_path, w) for w in token_windows(text)]


def code_fence_spans(text: str) -> list[tuple[int, int]]:
    """Char ranges inside fenced code blocks (``` or ~~~).

    pandoc-converted books DO fence their code, yet a `# Create a Spark DataFrame`
    comment inside a fence still matches MD_HEADER_RE and fabricates a section boundary.
    Header detection skips any match whose start falls inside one of these spans. An
    unterminated fence swallows the rest of the document (matches pandoc/CommonMark).
    """
    spans: list[tuple[int, int]] = []
    open_at: int | None = None
    for m in FENCE_RE.finditer(text):
        if open_at is None:
            open_at = m.start()
        else:
            spans.append((open_at, m.end()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def is_real_header(title: str) -> bool:
    """Distinguish a genuine markdown heading from a code comment that trafilatura
    emitted as a `#`-prefixed line. trafilatura's web→markdown output does NOT fence
    code (so `code_fence_spans` can't help there), and Python/shell comments
    (`# check the partitions data`) otherwise match the header regex and fabricate
    section boundaries.

    Capital/digit-led lines are real headings. A lowercase-led line is a real heading
    only when it looks like a code identifier — a method or config name such as
    `countDistinct`, `toPandas()`, or `spark.sql.shuffle.partitions` (single token, or
    dotted) — and NOT multi-word prose like `check the partitions data`. This keeps the
    lowercase API/config headings that a pure capital-led rule would wrongly drop.
    """
    t = title.strip()
    if not t:
        return False
    if t[0].isupper() or t[0].isdigit():
        return True
    return " " not in t or "." in t.split()[0]


def chunk_markdown(text: str, fallback_path: str) -> list[tuple[str, str]]:
    """Split markdown on h1-h3 boundaries, sub-split large sections, merge tiny ones."""
    fences = code_fence_spans(text)
    matches = [
        m
        for m in MD_HEADER_RE.finditer(text)
        if not any(start <= m.start() < end for start, end in fences) and is_real_header(m.group(2))
    ]

    segments: list[tuple[str, str]] = []  # (section_path, body)
    stack: list[str] = []

    if not matches:
        return chunk_by_tokens(text, fallback_path) if text.strip() else []

    if matches[0].start() > 0:
        preamble = text[: matches[0].start()]
        if preamble.strip():
            segments.append((fallback_path, preamble))

    for idx, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        stack = stack[: level - 1]
        stack.append(title)
        section_path = " > ".join(stack)

        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        segments.append((section_path, match.group(0) + body))

    # Sub-split oversized segments.
    expanded: list[tuple[str, str]] = []
    for section_path, body in segments:
        if count_tokens(body) > MAX_CHUNK_TOKENS:
            expanded.extend((section_path, w) for w in token_windows(body))
        else:
            expanded.append((section_path, body))

    # Merge undersized segments into the following one.
    merged: list[tuple[str, str]] = []
    pending: tuple[str, str] | None = None
    for section_path, body in expanded:
        if pending is not None:
            section_path = pending[0]
            body = pending[1] + "\n" + body
            pending = None
        if count_tokens(body) < MERGE_BELOW_TOKENS:
            pending = (section_path, body)
            continue
        merged.append((section_path, body))
    if pending is not None:
        if merged:
            prev_path, prev_body = merged[-1]
            merged[-1] = (prev_path, prev_body + "\n" + pending[1])
        else:
            merged.append(pending)

    return merged


def doc_pullback(text: str, region_start: int, def_start: int) -> int:
    """If a `/** ... */` ScalaDoc block sits directly above `def_start` (only whitespace
    between its close and the def), return the doc's start index; else `def_start`.

    Without this, a method's ScalaDoc — the NL-rich text that aligns with questions —
    lands at the tail of the PREVIOUS method's chunk (segments span def-to-def), so it
    gets attributed to the wrong method and never embeds near its own signature.
    """
    region = text[region_start:def_start]
    j = region.rfind(SCALADOC_OPEN)
    if j == -1:
        return def_start
    close = region.find("*/", j)
    if close == -1:
        return def_start
    if region[close + 2 :].strip():  # non-whitespace between */ and def → not attached
        return def_start
    return region_start + j


def split_leading_doc(body: str) -> tuple[str | None, str]:
    """Split a segment into (leading ScalaDoc or None, remaining code)."""
    lead_ws = len(body) - len(body.lstrip())
    if body[lead_ws:].startswith(SCALADOC_OPEN):
        close = body.find("*/", lead_ws)
        if close != -1:
            return body[: close + 2], body[close + 2 :]
    return None, body


def chunk_scala(text: str, fallback_path: str) -> list[tuple[str, str]]:
    """Split Scala source on top-level def/class/object/trait boundaries, keeping each
    method's ScalaDoc with its own method and emitting the doc as a separate NL-aligned
    chunk so its embedding is not diluted by the implementation body."""
    matches = list(SCALA_DEF_RE.finditer(text))
    if not matches:
        return chunk_by_tokens(text, fallback_path)

    # Pull each boundary back over a directly-preceding ScalaDoc so a method's doc lands
    # in ITS segment, not the previous method's.
    starts = [
        doc_pullback(text, matches[idx - 1].start() if idx > 0 else 0, match.start())
        for idx, match in enumerate(matches)
    ]

    enclosing = fallback_path
    segments: list[tuple[str, str]] = []

    if starts[0] > 0:
        preamble = text[: starts[0]]
        if preamble.strip():
            segments.append((fallback_path, preamble))

    for idx, match in enumerate(matches):
        kind = match.group(2)
        name = match.group(3)
        if kind in ("class", "object", "trait", "case class"):
            enclosing = name
            section_path = name
        else:
            section_path = f"{enclosing} > {name}"

        start = starts[idx]
        end = starts[idx + 1] if idx + 1 < len(matches) else len(text)
        segments.append((section_path, text[start:end]))

    # Split each segment's leading ScalaDoc into its own chunk (signature prepended for
    # context), then keep the code as its own chunk.
    split_segments: list[tuple[str, str]] = []
    for section_path, body in segments:
        doc, code = split_leading_doc(body)
        if doc and doc.strip():
            signature = next((line.strip() for line in code.splitlines() if line.strip()), "")
            doc_chunk = f"{signature}\n{doc.strip()}" if signature else doc.strip()
            split_segments.append((section_path, doc_chunk))
        if code.strip():
            split_segments.append((section_path, code))

    expanded: list[tuple[str, str]] = []
    for section_path, body in split_segments:
        if count_tokens(body) > MAX_CHUNK_TOKENS:
            expanded.extend((section_path, w) for w in token_windows(body))
        else:
            expanded.append((section_path, body))

    return expanded


def resolve_source_map(index: dict) -> tuple[dict[Path, dict], list[tuple[Path, dict]]]:
    """Build lookup tables: exact file -> source, and book directory -> source."""
    file_map: dict[Path, dict] = {}
    dir_map: list[tuple[Path, dict]] = []

    for source in index["sources"]:
        local = source.get("local")
        if not local:
            continue
        path = (REPO_ROOT / local).resolve()
        if source["type"] == "book":
            dir_map.append((path, source))
        else:
            file_map[path] = source

    return file_map, dir_map


def lookup_source(path: Path, file_map: dict[Path, dict], dir_map: list[tuple[Path, dict]]) -> dict:
    resolved = path.resolve()
    if resolved in file_map:
        return file_map[resolved]
    for dir_path, source in dir_map:
        if dir_path in resolved.parents:
            return source
    return {"id": path.stem, "version_bucket": "n/a"}


def iter_reference_files(references_dir: Path) -> list[Path]:
    files = []
    for ext in ("*.md", "*.txt", "*.scala"):
        files.extend(sorted(references_dir.rglob(ext)))
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=list(CORPORA), default="spark")
    args = parser.parse_args()
    corpus = CORPORA[args.corpus]

    index = yaml.safe_load(corpus.index_path.read_text())
    file_map, dir_map = resolve_source_map(index)

    console.print(f"loading embedding model [bold]{corpus.embedding_model}[/bold]...")
    model = SentenceTransformer(corpus.embedding_model)

    # Full wipe, not delete_collection: the latter leaves orphaned per-segment UUID dirs
    # and grows chroma.sqlite3 on every rebuild. Removing the whole store keeps rebuilds
    # clean and matches the full-rebuild-on-any-change policy.
    if corpus.chroma_path.exists():
        shutil.rmtree(corpus.chroma_path)
    client = chromadb.PersistentClient(path=str(corpus.chroma_path))
    collection = client.create_collection(corpus.collection_name)

    files = iter_reference_files(corpus.references_dir)
    console.print(f"found {len(files)} reference files")
    skipped_out_of_scope = 0

    all_ids: list[str] = []
    all_docs: list[str] = []
    all_metas: list[dict] = []
    per_source_count: dict[str, int] = {}

    for path in files:
        source = lookup_source(path, file_map, dir_map)

        # Book chapter pruning: if a book entry declares an in-scope `chapters` list,
        # index only files whose basename starts with one of those prefixes (e.g. "ch08").
        # Keeps out-of-scope chapters (streaming, ML, genomics) out of retrieval noise.
        if source.get("type") == "book":
            chapters = source.get("chapters")
            if chapters and not any(path.stem.startswith(prefix) for prefix in chapters):
                skipped_out_of_scope += 1
                continue

        source_id = source["id"]
        version_bucket = source.get("version_bucket", "n/a")
        fallback_path = path.relative_to(REPO_ROOT).as_posix()

        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue

        if path.suffix == ".md":
            chunks = chunk_markdown(text, fallback_path)
        elif path.suffix == ".scala":
            chunks = chunk_scala(text, fallback_path)
        else:  # .txt
            chunks = chunk_by_tokens(text, fallback_path)

        for chunk_idx, (section_path, body) in enumerate(chunks):
            if not body.strip():
                continue
            all_ids.append(f"{source_id}::{fallback_path}::{chunk_idx}")
            all_docs.append(body)
            all_metas.append(
                {
                    "source_id": source_id,
                    "version_bucket": version_bucket,
                    "section_path": section_path,
                    "chunk_idx": chunk_idx,
                    "local_path": fallback_path,
                }
            )
            per_source_count[source_id] = per_source_count.get(source_id, 0) + 1

    if skipped_out_of_scope:
        console.print(f"skipped {skipped_out_of_scope} out-of-scope book chapter file(s) (see index.yaml `chapters:`)")
    console.print(f"embedding {len(all_docs)} chunks from {len(per_source_count)} sources...")
    batch_size = 64
    for i in range(0, len(all_docs), batch_size):
        batch_docs = all_docs[i : i + batch_size]
        batch_ids = all_ids[i : i + batch_size]
        batch_metas = all_metas[i : i + batch_size]
        embeddings = model.encode(batch_docs, show_progress_bar=False, normalize_embeddings=True).tolist()
        collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas, embeddings=embeddings)
        console.print(f"  {min(i + batch_size, len(all_docs))}/{len(all_docs)}")

    console.print(f"[green]done.[/green] {len(all_docs)} chunks persisted to {corpus.chroma_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
