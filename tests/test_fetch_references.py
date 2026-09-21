"""fetch_references.py's real logic: JIRA key extraction, the empty-input
short circuit in html_to_markdown, and main()'s per-source status
categorization (ok/thin/failed/skipped) and failure aggregation. The actual
network fetchers (fetch_web/fetch_source/fetch_paper/fetch_jira) do live I/O
and stay untested — main() exercises them only through fakes.
"""
import pytest
import yaml

import scripts.fetch_references as fetch_references
from scripts.fetch_references import JIRA_KEY_RE, html_to_markdown


def test_html_to_markdown_empty_input_short_circuits_without_calling_pandoc(monkeypatch):
    def fail_if_called(*a, **k):
        raise AssertionError("subprocess.run should not be called for empty html")

    monkeypatch.setattr(fetch_references.subprocess, "run", fail_if_called)
    assert html_to_markdown("") == ""


def test_jira_key_re_extracts_project_and_number():
    match = JIRA_KEY_RE.search("https://issues.apache.org/jira/browse/SPARK-1234")
    assert match.group(1) == "SPARK-1234"


def test_jira_key_re_no_match_for_url_without_browse_path():
    assert JIRA_KEY_RE.search("https://issues.apache.org/jira/SPARK-1234") is None


def _write_index(path, sources):
    path.write_text(yaml.safe_dump({"sources": sources}), encoding="utf-8")


def _run_main(tmp_path, monkeypatch, sources, **fakes):
    index_path = tmp_path / "index.yaml"
    _write_index(index_path, sources)
    monkeypatch.setattr(fetch_references, "INDEX_PATH", index_path)
    monkeypatch.setattr(fetch_references, "REPO_ROOT", tmp_path)
    for name, fn in fakes.items():
        monkeypatch.setattr(fetch_references, name, fn)
    return fetch_references.main()


def test_book_source_is_skipped_without_fetching(tmp_path, monkeypatch):
    sources = [{"id": "b1", "type": "book", "local": "references/b1.md",
                "version_bucket": "n/a", "min_bytes": 10}]
    rc = _run_main(tmp_path, monkeypatch, sources)
    assert rc == 0
    assert not (tmp_path / "references" / "b1.md").exists()


def test_web_source_below_min_bytes_is_thin_and_fails_the_run(tmp_path, monkeypatch):
    sources = [{"id": "w1", "type": "web", "url": "https://example.com", "local": "references/w1.md",
                "version_bucket": "3.5", "min_bytes": 1000}]
    rc = _run_main(tmp_path, monkeypatch, sources, fetch_web=lambda source: ("short", 5))
    assert rc == 1
    assert (tmp_path / "references" / "w1.md").read_text() == "short"


def test_web_source_above_min_bytes_is_ok_and_run_succeeds(tmp_path, monkeypatch):
    sources = [{"id": "w1", "type": "web", "url": "https://example.com", "local": "references/w1.md",
                "version_bucket": "3.5", "min_bytes": 4}]
    rc = _run_main(tmp_path, monkeypatch, sources, fetch_web=lambda source: ("enough text", 11))
    assert rc == 0


def test_fetcher_exception_marks_source_failed_but_other_sources_still_run(tmp_path, monkeypatch):
    sources = [
        {"id": "bad", "type": "web", "url": "https://example.com", "local": "references/bad.md",
         "version_bucket": "3.5", "min_bytes": 1},
        {"id": "good", "type": "source", "url": "https://example.com/raw", "local": "references/good.md",
         "version_bucket": "3.5", "min_bytes": 1},
    ]

    def flaky_fetch_web(source):
        raise RuntimeError("network exploded")

    rc = _run_main(
        tmp_path, monkeypatch, sources,
        fetch_web=flaky_fetch_web,
        fetch_source=lambda source: ("ok content", 10),
    )

    assert rc == 1  # one failure fails the whole run
    assert not (tmp_path / "references" / "bad.md").exists()
    assert (tmp_path / "references" / "good.md").read_text() == "ok content"


def test_unknown_source_type_is_treated_as_a_failure(tmp_path, monkeypatch):
    sources = [{"id": "x", "type": "mystery", "local": "references/x.md",
                "version_bucket": "n/a", "min_bytes": 1}]
    rc = _run_main(tmp_path, monkeypatch, sources)
    assert rc == 1
    assert not (tmp_path / "references" / "x.md").exists()


def test_all_sources_ok_returns_0(tmp_path, monkeypatch):
    sources = [{"id": "w1", "type": "web", "url": "https://example.com", "local": "references/w1.md",
                "version_bucket": "3.5", "min_bytes": 1}]
    rc = _run_main(tmp_path, monkeypatch, sources, fetch_web=lambda source: ("x", 1))
    assert rc == 0
