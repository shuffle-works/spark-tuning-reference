"""Report content-page staleness against the section projection each page is
assembled from. Does NOT write page prose — only reports and (with --accept)
stamps the hash sidecar.

Usage:
  uv run python -m scripts.content_state              # report
  uv run python -m scripts.content_state --accept content/bottlenecks/skew.md
  uv run python -m scripts.content_state --check      # CI gate: exit non-zero if any page is stale
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

# Allow running as a file (uv run scripts/content_state.py) as CI does, not only -m.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.corpus import CORPORA  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def page_hash(projection_path: Path) -> str:
    return hashlib.sha256(Path(projection_path).read_bytes()).hexdigest()


def load_state(path: Path) -> dict:
    p = Path(path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.exists() else {}


def save_state(state: dict, path: Path) -> None:
    Path(path).write_text(yaml.safe_dump(state, sort_keys=True), encoding="utf-8")


def _entries(manifest: dict):
    for group in manifest["groups"]:
        yield from group["entries"]


def report(manifest: dict, state: dict, root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in _entries(manifest):
        digest = page_hash(Path(root) / entry["assembled_from"])
        recorded = state.get(entry["file"], {}).get("generated_from_hash")
        if recorded is None:
            out[entry["file"]] = "ungenerated"
        elif recorded != digest:
            out[entry["file"]] = "stale"
        else:
            out[entry["file"]] = "ok"
    return out


def accept(state: dict, page: str, digest: str) -> None:
    state[page] = {"generated_from_hash": digest}


def gate(statuses: dict[str, str]) -> int:
    """CI staleness gate: non-zero exit if any page is not 'ok'."""
    return 1 if any(s != "ok" for s in statuses.values()) else 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--accept", metavar="PAGE")
    p.add_argument("--corpus", choices=list(CORPORA), default="spark")
    p.add_argument("--check", action="store_true",
                   help="exit non-zero if any page is stale/ungenerated (CI gate)")
    args = p.parse_args(argv)
    corpus = CORPORA[args.corpus]
    manifest = yaml.safe_load(corpus.manifest_path.read_text(encoding="utf-8"))
    state = load_state(corpus.content_state_path)
    if args.accept:
        entry = next(e for e in _entries(manifest) if e["file"] == args.accept)
        accept(state, args.accept, page_hash(REPO_ROOT / entry["assembled_from"]))
        save_state(state, corpus.content_state_path)
        print(f"accepted {args.accept}")
        return 0
    statuses = report(manifest, state, REPO_ROOT)
    for page, status in statuses.items():
        if status != "ok":
            print(f"{status:12} {page}")
    stale = [p for p, s in statuses.items() if s != "ok"]
    print(f"{len(stale)} page(s) need attention" if stale else "all pages up to date")
    if stale and args.check:
        print("To fix: regenerate the page(s) and run "
              "`uv run scripts/content_state.py --accept <page>` for each.")
    return gate(statuses) if args.check else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
