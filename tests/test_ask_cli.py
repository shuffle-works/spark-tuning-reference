"""Coverage for ask.py's pure helpers and main()'s error/dispatch branching.
retrieve() itself is covered by test_retrieve.py; this file exercises what
that one doesn't: argument parsing, source-URL lookup, chunk formatting, and
the CLI's index-missing / collection-open-failure error paths.
"""
import dataclasses

import yaml

import scripts.ask as ask
from scripts.ask import Chunk, QuestionResult, format_result, load_source_urls, parse_args


def _corpus_with_chroma_path(path):
    # Corpus is a frozen dataclass; swap the CORPORA["spark"] entry via
    # dataclasses.replace() rather than mutating fields in place.
    return dataclasses.replace(ask.CORPORA["spark"], chroma_path=path)


def test_parse_args_defaults():
    args = parse_args(["what is a shuffle?"])
    assert args.questions == ["what is a shuffle?"]
    assert args.version is None
    assert args.k == ask.DEFAULT_K
    assert args.corpus == "spark"


def test_parse_args_collects_multiple_questions_and_flags():
    args = parse_args(["--version", "3.5", "--k", "5", "--corpus", "meta", "q1", "q2"])
    assert args.questions == ["q1", "q2"]
    assert args.version == "3.5"
    assert args.k == 5
    assert args.corpus == "meta"


def test_parse_args_rejects_unknown_version_bucket():
    import pytest

    with pytest.raises(SystemExit):
        parse_args(["--version", "2.0", "q"])


def test_load_source_urls_maps_id_to_url(tmp_path):
    index_path = tmp_path / "index.yaml"
    index_path.write_text(
        yaml.safe_dump({"sources": [{"id": "spark-tuning", "url": "https://example.com/tuning"}]}),
        encoding="utf-8",
    )
    assert load_source_urls(index_path) == {"spark-tuning": "https://example.com/tuning"}


def test_load_source_urls_defaults_missing_url_to_na(tmp_path):
    index_path = tmp_path / "index.yaml"
    index_path.write_text(
        yaml.safe_dump({"sources": [{"id": "book-x"}]}),
        encoding="utf-8",
    )
    assert load_source_urls(index_path) == {"book-x": "n/a"}


def test_format_result_indents_multiline_chunk_text():
    chunk = Chunk(
        rank=1, source_id="spark-tuning", text="line one\nline two",
        meta={"source_id": "spark-tuning", "version_bucket": "3.5",
              "local_path": "references/a.md", "section_path": "Tuning > Shuffle"},
        relevance=0.75, url="https://example.com",
    )
    out = format_result(chunk)
    assert "[1] spark-tuning" in out
    assert "relevance: 0.750" in out
    assert "        line one" in out
    assert "        line two" in out
    assert "url: https://example.com" in out


def test_main_reports_error_and_returns_1_when_index_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.setitem(ask.CORPORA, "spark", _corpus_with_chroma_path(tmp_path / "does-not-exist"))
    monkeypatch.setattr(ask.sys, "argv", ["ask.py", "some question"])

    rc = ask.main()

    assert rc == 1
    assert "no index at" in capsys.readouterr().out


def test_main_reports_error_and_returns_1_when_collection_open_fails(monkeypatch, capsys, tmp_path):
    monkeypatch.setitem(ask.CORPORA, "spark", _corpus_with_chroma_path(tmp_path))  # tmp_path exists

    def failing_open_collection(corpus):
        raise RuntimeError("no such collection")

    monkeypatch.setattr(ask, "open_collection", failing_open_collection)
    monkeypatch.setattr(ask.sys, "argv", ["ask.py", "some question"])

    rc = ask.main()

    assert rc == 1
    assert "could not open collection" in capsys.readouterr().out


def test_main_prints_no_chunks_found_when_retrieve_returns_empty(monkeypatch, capsys, tmp_path):
    monkeypatch.setitem(ask.CORPORA, "spark", _corpus_with_chroma_path(tmp_path))
    monkeypatch.setattr(ask, "open_collection", lambda corpus: object())
    monkeypatch.setattr(ask, "load_model", lambda corpus: object())
    monkeypatch.setattr(
        ask, "retrieve",
        lambda questions, **kw: [QuestionResult(question=questions[0], chunks=[], source_ids=[])],
    )
    monkeypatch.setattr(ask.sys, "argv", ["ask.py", "some question"])

    rc = ask.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "no chunks found" in out
    assert "citable source_ids (question 1/1, rank order): (none)" in out


def test_main_prints_chunks_and_version_filter_on_success(monkeypatch, capsys, tmp_path):
    monkeypatch.setitem(ask.CORPORA, "spark", _corpus_with_chroma_path(tmp_path))
    monkeypatch.setattr(ask, "open_collection", lambda corpus: object())
    monkeypatch.setattr(ask, "load_model", lambda corpus: object())
    chunk = Chunk(
        rank=1, source_id="spark-tuning", text="chunk text",
        meta={"source_id": "spark-tuning", "version_bucket": "3.5",
              "local_path": "references/a.md", "section_path": "Tuning"},
        relevance=0.5, url="n/a",
    )
    monkeypatch.setattr(
        ask, "retrieve",
        lambda questions, **kw: [
            QuestionResult(question=questions[0], chunks=[chunk], source_ids=["spark-tuning"])
        ],
    )
    monkeypatch.setattr(ask.sys, "argv", ["ask.py", "--version", "3.5", "some question"])

    rc = ask.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "version filter: 3.5 (+ n/a)" in out
    assert "chunk text" in out
    assert "citable source_ids (question 1/1, rank order): spark-tuning" in out
