"""Validate content/manifest.yaml <-> research/answers mapping (backlog C1).

Every manifest entry must carry `assembled_from:` pointing to an existing answer file,
and every answer file must be referenced by at least one entry. Anchors themselves are
the frozen cross-repo contract and are NOT checked or altered here (spark corpus only —
see docs/rules/content.md #3; the meta corpus's content/meta/manifest.yaml carries no
such contract).
"""

import argparse
import sys
from pathlib import Path

import yaml

from scripts.corpus import CORPORA


def collect_errors(manifest_path: Path, answers_dir: Path) -> list[str]:
    """Return mapping errors (empty list == OK). Reusable by scripts/prebuild_checks.py."""
    manifest = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))
    entries = [e for g in manifest["groups"] for e in g["entries"]]
    answer_files = {p.name for p in Path(answers_dir).glob("*.md")}

    errors: list[str] = []
    referenced: set[str] = set()
    for e in entries:
        src = e.get("assembled_from")
        if not src:
            errors.append(f"entry anchor={e.get('anchor')} missing assembled_from")
            continue
        name = Path(src).name
        if name not in answer_files:
            errors.append(f"entry anchor={e.get('anchor')} assembled_from missing on disk: {src}")
        referenced.add(name)

    for orphan in sorted(answer_files - referenced):
        errors.append(f"answer file never referenced by any manifest entry: {orphan}")
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", choices=list(CORPORA), default="spark")
    args = p.parse_args()
    corpus = CORPORA[args.corpus]

    manifest = yaml.safe_load(corpus.manifest_path.read_text(encoding="utf-8"))
    entries = [e for g in manifest["groups"] for e in g["entries"]]
    answer_files = {p.name for p in corpus.answers_dir.glob("*.md")}
    errors = collect_errors(corpus.manifest_path, corpus.answers_dir)

    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} mapping error(s).")
        return 1
    print(f"OK: {len(entries)} entries, all assembled_from valid; "
          f"{len(answer_files)} answer files all referenced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
