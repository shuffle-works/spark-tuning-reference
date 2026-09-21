"""Generate anchors.json, the frozen projection of content/manifest.yaml
that sparkforensics' detector-coverage check reads (docs/anchor-map.md).

Ported from the retired Node build's projectAnchors() (site/render.mjs); this is
the spark corpus's public surface only, never content/meta/manifest.yaml.

Run: uv run scripts/build_anchors.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "content" / "manifest.yaml"
OUTPUT_PATH = ROOT / "anchors.json"


def project_anchors(manifest: dict) -> list[dict]:
    anchors = []
    for group in manifest["groups"]:
        for entry in group["entries"]:
            anchors.append({
                "anchor": entry["anchor"],
                "section": group["title"],
                "title": entry["title"],
                "keywords": entry.get("keywords", []),
            })
    return anchors


def main() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    anchors = project_anchors(manifest)
    OUTPUT_PATH.write_text(json.dumps(anchors, indent=2) + "\n", encoding="utf-8")
    print(f"built {OUTPUT_PATH} ({len(anchors)} anchors)")


if __name__ == "__main__":
    main()
