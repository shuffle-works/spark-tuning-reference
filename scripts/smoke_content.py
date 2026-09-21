"""Content-source smoke checks (formerly ran over the built HTML; the HTML
build moved upstream, so this now checks content/*.md directly — the same
invariants, verified before rendering rather than after).

Run: uv run scripts/smoke_content.py
Asserts: 31 manifest entries, each with an existing content file; every
sub-anchor's `{#id}` heading attribute present somewhere in the entries' files;
no dangling footnote reference; no fenced code nested inside a blockquote.
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = yaml.safe_load((ROOT / "content" / "manifest.yaml").read_text(encoding="utf-8"))
ENTRIES = [(e["anchor"], ROOT / e["file"]) for g in MANIFEST["groups"] for e in g["entries"]]

errors: list[str] = []

# 1. Every frozen manifest anchor has its content file on disk.
for anchor, path in ENTRIES:
    if not path.exists():
        errors.append(f"manifest entry #{anchor}: missing content file {path.relative_to(ROOT)}")
if len(ENTRIES) != 31:
    errors.append(f"expected 31 manifest anchors, found {len(ENTRIES)}")

SOURCES = {anchor: path.read_text(encoding="utf-8") for anchor, path in ENTRIES if path.exists()}
ALL_SOURCE = "\n".join(SOURCES.values())

# 1b. Sub-anchors: not manifest entries (they live inside a section's page via
#     a Markdown `{#id}` heading attribute), so the loop above does not cover
#     them. They are a frozen cross-repo contract with sparkforensics.
SUB_ANCHORS = [
    "config-shuffle-service",
    "config-autoscale-bounds",
    "config-serializer",
    "config-memory-overhead",
    # Experimental stage-level detector subsections (SHAPE lives under skew,
    # SLOW under slow-host); their detectors deep-link to these ids.
    "bottleneck-stage-shape",
    "bottleneck-stage-slowness",
]
for anchor in SUB_ANCHORS:
    if f"{{#{anchor}}}" not in ALL_SOURCE:
        errors.append(f"missing sub-anchor heading: {{#{anchor}}}")

# 2. No dangling footnote reference: every `[^id]` needs a same-file `[^id]: ...`
#    definition line.
for anchor, text in SOURCES.items():
    refs = set(re.findall(r"\[\^([^\]]+)\]", text))
    defs = set(re.findall(r"^\[\^([^\]]+)\]:", text, re.MULTILINE))
    for ref in sorted(refs - defs):
        errors.append(f"{anchor}: dangling footnote reference [^{ref}] (no [^{ref}]: definition)")

# 3. Fenced-code-in-blockquote breakage: python-markdown does not render a ```
#    fence nested inside a blockquote (docs/rules/content.md #4). No contiguous
#    run of `>`-prefixed lines may contain one.
for anchor, text in SOURCES.items():
    for block in re.findall(r"(?:^>.*\n?)+", text, re.MULTILINE):
        if "```" in block:
            errors.append(f"{anchor}: literal ``` fence found inside a blockquote")

if errors:
    print("\n".join(errors))
    print(f"\n{len(errors)} smoke error(s).")
    sys.exit(1)
print(f"OK: 31 sections, all {len(ENTRIES)} anchors + {len(SUB_ANCHORS)} sub-anchors present, "
      f"no dangling footnotes, no fence-in-blockquote.")
