"""Append a question to the registry (append-only). Prints the new id.

Usage: uv run python -m scripts.add_question "<text>" --section 3.6-shuffle [--version 3.5] [--k 18]
"""
from __future__ import annotations

import argparse
import sys

from scripts.corpus import CORPORA
from scripts.registry import (
    Question, Registry, load_registry, next_question_id, save_registry,
    VALID_VERSION,
)


def add_question(reg: Registry, text: str, section_id: str, version: str, k: int | None) -> str:
    qid = next_question_id(reg, section_id)
    reg.questions.append(Question(qid, section_id, text, version, k, "pending"))
    return qid


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--section", required=True)
    p.add_argument("--version", choices=VALID_VERSION, default="n/a")
    p.add_argument("--k", type=int, default=None)
    p.add_argument("--corpus", choices=list(CORPORA), default="spark")
    args = p.parse_args(argv)
    reg = load_registry(CORPORA[args.corpus].questions_path)
    if not any(s.id == args.section for s in reg.sections):
        print(f"error: unknown section {args.section}", file=sys.stderr)
        return 1
    qid = add_question(reg, args.text, args.section, args.version, args.k)
    save_registry(reg, CORPORA[args.corpus].questions_path)
    print(qid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
