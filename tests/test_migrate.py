from scripts.migrate_to_registry import parse_section_file, used_footnotes, per_question_file

SECTION = """\
# Shuffle

## What triggers a shuffle?

Wide transforms[^a] and joins[^b].

## Sort vs hash?

Sort-based by default[^a].

## Sources

[^a]: a — http://a
[^b]: b — http://b
"""

def test_parse_splits_into_question_blocks():
    title, blocks = parse_section_file(SECTION)
    assert title == "Shuffle"
    assert [h for h, _ in blocks] == ["What triggers a shuffle?", "Sort vs hash?"]

def test_used_footnotes_first_seen_order():
    assert used_footnotes("x[^b] y[^a] z[^b]") == ["b", "a"]

def test_per_question_file_carries_only_used_defs():
    _, blocks = parse_section_file(SECTION)
    defs = {"a": "[^a]: a — http://a", "b": "[^b]: b — http://b"}
    out = per_question_file(blocks[1][1], defs)
    assert "[^a]: a — http://a" in out
    assert "[^b]:" not in out            # q2 only cites ^a
    assert out.startswith("## Sort vs hash?")
    assert "## Sources" in out
