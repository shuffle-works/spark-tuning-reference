"""Named corpus profiles: every path and model constant a pipeline script
needs, for each of the two independent RAG pipelines this repo runs.

Every script that touches a corpus-specific path takes a --corpus flag
(default "spark") and looks up its profile here instead of hardcoding a
module constant, so the same script serves both pipelines unmodified.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Corpus:
    references_dir: Path
    index_path: Path
    chroma_path: Path
    collection_name: str
    embedding_model: str
    questions_path: Path
    answers_q_dir: Path
    answers_dir: Path
    content_state_path: Path
    manifest_path: Path


SPARK = Corpus(
    references_dir=REPO_ROOT / "references",
    index_path=REPO_ROOT / "references" / "index.yaml",
    chroma_path=REPO_ROOT / ".chromadb",
    collection_name="spark_docs",
    embedding_model="multi-qa-mpnet-base-dot-v1",
    questions_path=REPO_ROOT / "research" / "questions.yaml",
    answers_q_dir=REPO_ROOT / "research" / "answers" / "q",
    answers_dir=REPO_ROOT / "research" / "answers",
    content_state_path=REPO_ROOT / "research" / "content-state.yaml",
    manifest_path=REPO_ROOT / "content" / "manifest.yaml",
)

META = Corpus(
    references_dir=REPO_ROOT / "references-meta",
    index_path=REPO_ROOT / "references-meta" / "index.yaml",
    chroma_path=REPO_ROOT / ".chromadb-meta",
    collection_name="meta_docs",
    embedding_model="all-mpnet-base-v2",
    questions_path=REPO_ROOT / "research" / "meta" / "questions.yaml",
    answers_q_dir=REPO_ROOT / "research" / "meta" / "answers" / "q",
    answers_dir=REPO_ROOT / "research" / "meta" / "answers",
    content_state_path=REPO_ROOT / "research" / "meta" / "content-state.yaml",
    manifest_path=REPO_ROOT / "content" / "meta" / "manifest.yaml",
)

CORPORA: dict[str, Corpus] = {"spark": SPARK, "meta": META}
