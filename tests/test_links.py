"""Link integrity over the content markdown SOURCE, stdlib + PyYAML only. (The
HTML build moved upstream, so this now checks source before rendering instead
of the built HTML it used to parse.)

For each corpus, for every content file: a `](#fragment)` link must resolve
either to a real manifest anchor in that corpus (a cross-reference to another
manifest entry — rewritten to a sibling page's `<anchor>.html` at build time,
see docs/rules/content.md #7) or to a `{#id}` heading attribute defined in that
SAME file (a genuine same-page fragment). Anything else is a dead link.
External http(s) links are out of scope (a separate issue).
"""
import re
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

LINK_RE = re.compile(r"\]\(#([^)\s]+)\)")
HEADING_ID_RE = re.compile(r"\{#([^}\s]+)\}")

CORPORA = [
    ("spark", "content/manifest.yaml"),
    ("meta", "content/meta/manifest.yaml"),
]


def _entries(manifest_path):
    manifest = yaml.safe_load((ROOT / manifest_path).read_text(encoding="utf-8"))
    return [(e["anchor"], ROOT / e["file"]) for g in manifest["groups"] for e in g["entries"]]


@pytest.mark.parametrize("corpus,manifest_path", CORPORA, ids=[c[0] for c in CORPORA])
def test_links(corpus, manifest_path):
    entries = _entries(manifest_path)
    manifest_anchors = {anchor for anchor, _ in entries}

    for anchor, path in entries:
        assert path.exists(), f"[{corpus}] manifest entry #{anchor}: missing content file {path.relative_to(ROOT)}"
        text = path.read_text(encoding="utf-8")
        same_page_ids = set(HEADING_ID_RE.findall(text))

        dead = sorted({
            frag for frag in LINK_RE.findall(text)
            if frag not in manifest_anchors and frag not in same_page_ids
        })
        assert not dead, (
            f"[{corpus}] {path.relative_to(ROOT)}: dead #fragment link(s) (resolve to neither a "
            f"manifest anchor nor a same-file heading id): {dead}"
        )
