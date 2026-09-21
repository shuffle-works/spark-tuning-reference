import yaml
from scripts.check_manifest_mapping import collect_errors


def _write_manifest(path, entries):
    path.write_text(yaml.safe_dump({"groups": [{"title": "G", "entries": entries}]}), encoding="utf-8")


def test_collect_errors_empty_when_all_assembled_from_present(tmp_path):
    answers_dir = tmp_path / "answers"
    answers_dir.mkdir()
    (answers_dir / "m1-pipeline-overview.md").write_text("# Pipeline Overview\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path, [
        {"file": "content/x.md", "anchor": "x", "title": "X",
         "assembled_from": "research/meta/answers/m1-pipeline-overview.md", "brief": "b"},
    ])
    assert collect_errors(manifest_path, answers_dir) == []


def test_collect_errors_flags_missing_assembled_from(tmp_path):
    answers_dir = tmp_path / "answers"
    answers_dir.mkdir()
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path, [
        {"file": "content/x.md", "anchor": "x", "title": "X",
         "assembled_from": "research/meta/answers/missing.md", "brief": "b"},
    ])
    errors = collect_errors(manifest_path, answers_dir)
    assert len(errors) == 1
    assert "missing on disk" in errors[0]


def test_collect_errors_flags_orphan_answer_file(tmp_path):
    answers_dir = tmp_path / "answers"
    answers_dir.mkdir()
    (answers_dir / "orphan.md").write_text("x", encoding="utf-8")
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path, [])
    errors = collect_errors(manifest_path, answers_dir)
    assert len(errors) == 1
    assert "orphan.md" in errors[0]


def test_collect_errors_empty_manifest_no_answers():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        answers_dir = d / "answers"
        answers_dir.mkdir()
        manifest_path = d / "manifest.yaml"
        _write_manifest(manifest_path, [])
        assert collect_errors(manifest_path, answers_dir) == []
