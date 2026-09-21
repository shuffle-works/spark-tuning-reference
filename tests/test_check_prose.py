import pytest

from scripts.check_prose import (
    diff_invariants,
    extract_invariants,
    lint_paths,
    lint_text,
    main,
    mask_for_lint,
)


def test_lint_text_flags_banned_phrase_with_category_and_line():
    errors = lint_text("This is a robust and seamless approach.\n")
    assert any("false_sophistication" in e and "'robust'" in e for e in errors)
    assert any(e.startswith("1:") for e in errors)


def test_lint_text_clean_prose_has_no_errors():
    assert lint_text("Shuffle spills to disk when partitions exceed memory.\n") == []


def test_lint_text_em_dash_over_max_is_flagged():
    errors = lint_text("Two stages run — one after the other.\n")
    assert any("em dash" in e for e in errors)


def test_lint_text_curly_quote_is_flagged():
    errors = lint_text("The default is “balanced”.\n")
    assert any("curly quote" in e for e in errors)


def test_lint_text_not_only_but_allowed_once_but_not_twice():
    once = "Not only does it spill, but it also retries.\n"
    assert lint_text(once) == []
    twice = once + "Not only does it retry, but it also fails.\n"
    errors = lint_text(twice)
    assert any("not only" in e for e in errors)


def test_mask_for_lint_blanks_fenced_code_but_keeps_line_count():
    text = "before\n```python\nleverage_this_and_that = 1\n```\nafter\n"
    masked = mask_for_lint(text)
    assert masked.count("\n") == text.count("\n")
    assert "leverage" not in masked
    assert "before" in masked and "after" in masked


def test_mask_for_lint_blanks_sources_section_and_headings():
    text = "## Some Heading\nbody text\n## Sources\n[^1]: https://example.com\n"
    masked = mask_for_lint(text)
    assert "Some Heading" not in masked
    assert "example.com" not in masked
    assert "body text" in masked


def test_mask_for_lint_blanks_front_matter():
    text = "---\ntitle: leverage this\n---\nbody\n"
    masked = mask_for_lint(text)
    assert "leverage" not in masked
    assert "body" in masked


def test_lint_text_ignores_banned_phrase_inside_fenced_code():
    text = "```\nleverage_broadcast = True\n```\n"
    assert lint_text(text) == []


def test_lint_paths_only_reports_files_with_issues(tmp_path):
    clean = tmp_path / "clean.md"
    clean.write_text("Nothing wrong here.\n", encoding="utf-8")
    dirty = tmp_path / "dirty.md"
    dirty.write_text("This showcases a robust design.\n", encoding="utf-8")

    results = lint_paths([tmp_path])
    assert str(clean) not in results
    assert str(dirty) in results
    assert len(results[str(dirty)]) >= 1


def test_extract_invariants_captures_footnotes_sources_and_numbers():
    text = (
        "## How much memory?\n"
        "It uses 4096 MB by default.[^a]\n\n"
        "## Sources\n"
        "[^a]: https://example.com\n"
    )
    inv = extract_invariants(text)
    # both the inline reference [^a] and its "[^a]:" definition line match the
    # token pattern, so a single footnote yields two entries.
    assert inv["footnote_tokens"] == ["[^a]", "[^a]"]
    assert inv["heading"] == "## How much memory?"
    assert "4096" in inv["numbers"]
    assert inv["sources_block"].startswith("## Sources")
    assert inv["unresourced_count"] == 0


def test_diff_invariants_flags_changed_footnotes():
    before = "## Q\nUses 10 executors.[^a]\n\n## Sources\n[^a]: x\n"
    after = "## Q\nUses 10 executors.\n\n## Sources\n[^a]: x\n"
    errors = diff_invariants(before, after)
    assert any("footnote tokens changed" in e for e in errors)


def test_diff_invariants_flags_changed_numbers():
    before = "## Q\nDefault is 200 partitions.\n\n## Sources\n"
    after = "## Q\nDefault is 400 partitions.\n\n## Sources\n"
    errors = diff_invariants(before, after)
    assert any("numeric tokens changed" in e for e in errors)


def test_diff_invariants_no_errors_when_only_wording_changes():
    before = "## Q\nSpark spills to disk under memory pressure.\n\n## Sources\n[^a]: x\n"
    after = "## Q\nSpark writes to disk when memory runs low.\n\n## Sources\n[^a]: x\n"
    assert diff_invariants(before, after) == []


def test_main_diff_mode_returns_1_and_reports_on_invariant_break(tmp_path, capsys):
    before = tmp_path / "before.md"
    after = tmp_path / "after.md"
    before.write_text("## Q\nUses 10 executors.[^a]\n\n## Sources\n[^a]: x\n", encoding="utf-8")
    after.write_text("## Q\nUses 10 executors.\n\n## Sources\n[^a]: x\n", encoding="utf-8")

    rc = main(["--diff", str(before), str(after)])
    assert rc == 1
    assert "invariant check failed" in capsys.readouterr().out


def test_main_lint_mode_returns_0_when_clean(tmp_path, capsys):
    clean = tmp_path / "clean.md"
    clean.write_text("Nothing wrong here.\n", encoding="utf-8")
    rc = main([str(clean)])
    assert rc == 0
    assert "no prose issues" in capsys.readouterr().out


def test_main_lint_mode_returns_1_when_dirty(tmp_path, capsys):
    dirty = tmp_path / "dirty.md"
    dirty.write_text("This showcases a robust design.\n", encoding="utf-8")
    rc = main([str(dirty)])
    assert rc == 1
    assert "prose issue" in capsys.readouterr().out


def test_main_requires_paths_or_diff(tmp_path):
    with pytest.raises(SystemExit):
        main([])
