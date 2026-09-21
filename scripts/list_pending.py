"""Print ids of questions with status: pending, one per line. Drives batch runs
(replaces the SECTIONS loop of the deleted step4-answering.js).

Usage: uv run python -m scripts.list_pending
"""
from __future__ import annotations

import argparse
import sys

from scripts.corpus import CORPORA
from scripts.registry import Registry, load_registry


def pending_ids(reg: Registry) -> list[str]:
    return [q.id for q in reg.questions if q.status == "pending"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", choices=list(CORPORA), default="spark")
    args = p.parse_args()
    for qid in pending_ids(load_registry(CORPORA[args.corpus].questions_path)):
        print(qid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
