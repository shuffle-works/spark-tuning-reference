from scripts.build_anchors import project_anchors


def test_project_anchors_carries_section_title_from_enclosing_group():
    manifest = {
        "groups": [
            {"title": "Shuffle", "entries": [
                {"anchor": "a1", "title": "Sort merge", "keywords": ["shuffle", "sort"]},
            ]},
            {"title": "Memory", "entries": [
                {"anchor": "a2", "title": "Off-heap", "keywords": ["memory"]},
            ]},
        ],
    }
    anchors = project_anchors(manifest)
    assert anchors == [
        {"anchor": "a1", "section": "Shuffle", "title": "Sort merge", "keywords": ["shuffle", "sort"]},
        {"anchor": "a2", "section": "Memory", "title": "Off-heap", "keywords": ["memory"]},
    ]


def test_project_anchors_defaults_missing_keywords_to_empty_list():
    manifest = {"groups": [{"title": "G", "entries": [{"anchor": "a1", "title": "T"}]}]}
    anchors = project_anchors(manifest)
    assert anchors[0]["keywords"] == []


def test_project_anchors_flattens_multiple_entries_per_group():
    manifest = {
        "groups": [
            {"title": "G", "entries": [
                {"anchor": "a1", "title": "T1"},
                {"anchor": "a2", "title": "T2"},
            ]},
        ],
    }
    anchors = project_anchors(manifest)
    assert [a["anchor"] for a in anchors] == ["a1", "a2"]


def test_project_anchors_empty_groups_yields_no_anchors():
    assert project_anchors({"groups": []}) == []


def test_project_anchors_group_with_no_entries_contributes_nothing():
    manifest = {"groups": [{"title": "Empty", "entries": []}, {"title": "G", "entries": [
        {"anchor": "a1", "title": "T"},
    ]}]}
    anchors = project_anchors(manifest)
    assert len(anchors) == 1
    assert anchors[0]["anchor"] == "a1"
