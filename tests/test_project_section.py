# tests/test_project_section.py
from pathlib import Path
from scripts.registry import Registry, Section, Question
from scripts.project_section import split_sources, merge_footnotes, build_projection

def test_split_sources_separates_body_and_defs():
    md = "## Q one\n\nText[^a].\n\n## Sources\n\n[^a]: a — http://a\n"
    body, defs = split_sources(md)
    assert body == "## Q one\n\nText[^a]."
    assert defs == {"a": "[^a]: a — http://a"}

def test_split_sources_no_sources_block():
    md = "## Q\n\nText.\n"
    body, defs = split_sources(md)
    assert body == "## Q\n\nText."
    assert defs == {}

def test_merge_footnotes_dedups_first_seen():
    merged = merge_footnotes([
        {"a": "[^a]: a", "b": "[^b]: b"},
        {"b": "[^b]: b", "c": "[^c]: c"},
    ])
    assert list(merged.keys()) == ["a", "b", "c"]

def test_build_projection_concats_in_registry_order(tmp_path):
    qdir = tmp_path / "q"
    qdir.mkdir()
    (qdir / "3.6-q01.md").write_text(
        "## First?\n\nAlpha[^a].\n\n## Sources\n\n[^a]: a — http://a\n", encoding="utf-8")
    (qdir / "3.6-q02.md").write_text(
        "## Second?\n\nBeta[^b].\n\n## Sources\n\n[^b]: b — http://b\n", encoding="utf-8")
    reg = Registry(
        sections=[Section("3.6-shuffle", "3.6", "Shuffle", 18)],
        questions=[
            Question("3.6-q01", "3.6-shuffle", "First?", "n/a", None, "answered"),
            Question("3.6-q02", "3.6-shuffle", "Second?", "n/a", None, "answered"),
        ],
    )
    out = build_projection(reg, "3.6-shuffle", qdir)
    assert out == (
        "# Shuffle\n\n"
        "## First?\n\nAlpha[^a].\n\n"
        "## Second?\n\nBeta[^b].\n\n"
        "## Sources\n\n"
        "[^a]: a — http://a\n"
        "[^b]: b — http://b\n"
    )

def test_build_projection_is_idempotent(tmp_path):
    qdir = tmp_path / "q"; qdir.mkdir()
    (qdir / "3.6-q01.md").write_text("## Q?\n\nX[^a].\n\n## Sources\n\n[^a]: a\n", encoding="utf-8")
    reg = Registry([Section("3.6-shuffle", "3.6", "Shuffle", 18)],
                   [Question("3.6-q01", "3.6-shuffle", "Q?", "n/a", None, "answered")])
    assert build_projection(reg, "3.6-shuffle", qdir) == build_projection(reg, "3.6-shuffle", qdir)
