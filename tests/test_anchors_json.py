import json
from pathlib import Path

import yaml

from scripts.build_anchors import project_anchors

ROOT = Path(__file__).resolve().parent.parent


def test_anchors_json_is_faithful_projection_of_manifest():
    manifest = yaml.safe_load((ROOT / "content" / "manifest.yaml").read_text(encoding="utf-8"))
    expected = {}
    for group in manifest["groups"]:
        for entry in group["entries"]:
            expected[entry["anchor"]] = (group["title"], entry["title"])

    anchors_path = ROOT / "anchors.json"
    anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
    by_anchor = {obj["anchor"]: obj for obj in anchors}
    assert set(by_anchor) == set(expected)  # identical anchor set

    for anchor, (section, title) in expected.items():
        obj = by_anchor[anchor]
        assert obj["section"] == section
        assert obj["title"] == title
        assert isinstance(obj["keywords"], list)

    # the committed file must be exactly what build_anchors.py emits today —
    # catches drift without shelling out or rewriting the file at test time.
    assert project_anchors(manifest) == anchors
