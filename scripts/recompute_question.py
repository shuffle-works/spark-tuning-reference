"""Flip a question to pending and back up its answer file, so the answer pipeline
can regenerate only that question. Touches no other record.

Usage: uv run python -m scripts.recompute_question <id>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.corpus import CORPORA
from scripts.registry import Registry, get_question, load_registry, save_registry


def recompute_question(reg: Registry, qid: str, answers_q_dir: Path) -> None:
    q = get_question(reg, qid)
    q.status = "pending"
    answer = Path(answers_q_dir) / f"{qid}.md"
    if answer.exists():
        answer.replace(answer.with_suffix(".md.bak"))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("qid")
    p.add_argument("--corpus", choices=list(CORPORA), default="spark")
    args = p.parse_args(argv)
    corpus = CORPORA[args.corpus]
    reg = load_registry(corpus.questions_path)
    try:
        recompute_question(reg, args.qid, corpus.answers_q_dir)
    except KeyError:
        print(f"error: unknown question {args.qid}", file=sys.stderr)
        return 1
    save_registry(reg, corpus.questions_path)
    print(f"{args.qid} → pending")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
