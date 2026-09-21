"""main()'s two gate conditions: a manifest-mapping error is fatal (exit 1,
before any staleness reporting runs); a stale/ungenerated content page is only
an advisory warning (exit 0). See scripts/prebuild_checks.py's module docstring.

content_report() hashes `entry["assembled_from"]` against prebuild_checks'
own REPO_ROOT (the real project root, not the corpus under test — see main()),
so `assembled_from` here must name a real .md file relative to that root
(collect_errors() only matches answer basenames ending in .md); CLAUDE.md is
a stable, always-present choice.
"""
import pytest
import yaml

from scripts.corpus import Corpus
from scripts.content_state import page_hash
import scripts.prebuild_checks as prebuild_checks

ASSEMBLED_FROM = "CLAUDE.md"  # real .md file under prebuild_checks.REPO_ROOT


def _corpus(tmp_path, entries, content_state=None):
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump({"groups": [{"title": "G", "entries": entries}]}), encoding="utf-8"
    )
    answers_dir = tmp_path / "answers"
    answers_dir.mkdir()
    # collect_errors() only checks basenames exist in answers_dir; content_report()
    # separately resolves assembled_from against the real repo root (see module docstring).
    (answers_dir / ASSEMBLED_FROM).write_text("placeholder", encoding="utf-8")
    content_state_path = tmp_path / "content-state.yaml"
    content_state_path.write_text(yaml.safe_dump(content_state or {}), encoding="utf-8")
    return Corpus(
        references_dir=tmp_path, index_path=tmp_path / "index.yaml", chroma_path=tmp_path / "chroma",
        collection_name="c", embedding_model="m", questions_path=tmp_path / "q.yaml",
        answers_q_dir=tmp_path / "q", answers_dir=answers_dir,
        content_state_path=content_state_path, manifest_path=manifest_path,
    )


def _entry(anchor, assembled_from):
    return {"anchor": anchor, "title": anchor, "file": f"content/{anchor}.md", "assembled_from": assembled_from}


@pytest.fixture(autouse=True)
def _argv(monkeypatch):
    monkeypatch.setattr("sys.argv", ["prebuild_checks.py"])


def test_manifest_mapping_error_is_fatal(tmp_path, monkeypatch, capsys):
    entries = [_entry("a1", "research/answers/missing.md")]
    corpus = _corpus(tmp_path, entries)
    monkeypatch.setitem(prebuild_checks.CORPORA, "spark", corpus)

    with pytest.raises(SystemExit) as exc:
        prebuild_checks.main()
    assert exc.value.code == 1
    assert "missing on disk" in capsys.readouterr().err


def test_stale_page_is_advisory_not_fatal(tmp_path, monkeypatch, capsys):
    entries = [_entry("a1", ASSEMBLED_FROM)]
    corpus = _corpus(tmp_path, entries)  # content-state.yaml empty -> ungenerated
    monkeypatch.setitem(prebuild_checks.CORPORA, "spark", corpus)

    prebuild_checks.main()  # must not raise/exit non-zero

    err = capsys.readouterr().err
    assert "out of sync" in err
    assert "ungenerated: content/a1.md" in err


def test_all_pages_up_to_date_prints_ok(tmp_path, monkeypatch, capsys):
    entries = [_entry("a1", ASSEMBLED_FROM)]
    corpus = _corpus(tmp_path, entries)
    digest = page_hash(prebuild_checks.REPO_ROOT / ASSEMBLED_FROM)
    corpus.content_state_path.write_text(
        yaml.safe_dump({"content/a1.md": {"generated_from_hash": digest}}), encoding="utf-8"
    )
    monkeypatch.setitem(prebuild_checks.CORPORA, "spark", corpus)

    prebuild_checks.main()

    out = capsys.readouterr().out
    assert "content pages: all up to date" in out
