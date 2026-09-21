"""Build a section projection (research/answers/<section-id>.md) by
concatenating its per-question answer files in registry order and merging their
per-question ## Sources blocks into one deduped block.

A projection is a pure function of its questions' answer files — fully regenerable.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from scripts.corpus import CORPORA
from scripts.registry import Registry, load_registry, questions_in

_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:\s")


def split_sources(md: str) -> tuple[str, dict[str, str]]:
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "## Sources":
            body = "\n".join(lines[:i]).rstrip()
            defs: dict[str, str] = {}
            for def_line in lines[i + 1:]:
                m = _DEF_RE.match(def_line)
                if m:
                    defs[m.group(1)] = def_line.rstrip()
            return body, defs
    return md.rstrip(), {}


def merge_footnotes(defs_in_order: list[dict[str, str]]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for defs in defs_in_order:
        for key, line in defs.items():
            if key not in merged:
                merged[key] = line
    return merged


def build_projection(reg: Registry, section_id: str, answers_q_dir: Path) -> str:
    section = next(s for s in reg.sections if s.id == section_id)
    bodies: list[str] = []
    all_defs: list[dict[str, str]] = []
    for q in questions_in(reg, section_id):
        text = (Path(answers_q_dir) / f"{q.id}.md").read_text(encoding="utf-8")
        body, defs = split_sources(text)
        bodies.append(body)
        all_defs.append(defs)
    merged = merge_footnotes(all_defs)
    parts = [f"# {section.title}", ""]
    for body in bodies:
        parts.append(body)
        parts.append("")
    parts.append("## Sources")
    parts.append("")
    parts.extend(merged.values())
    return "\n".join(parts) + "\n"


def write_projection(reg: Registry, section_id: str, answers_q_dir: Path, out_dir: Path) -> Path:
    out = Path(out_dir) / f"{section_id}.md"
    out.write_text(build_projection(reg, section_id, answers_q_dir), encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("section_ids", nargs="+", metavar="section-id")
    p.add_argument("--corpus", choices=list(CORPORA), default="spark")
    args = p.parse_args(argv)
    corpus = CORPORA[args.corpus]
    reg = load_registry(corpus.questions_path)
    for section_id in args.section_ids:
        path = write_projection(reg, section_id, corpus.answers_q_dir, corpus.answers_dir)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
