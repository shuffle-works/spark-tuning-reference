from pathlib import Path
import pytest
from scripts.registry import (
    Registry, Section, Question,
    load_registry, save_registry, questions_in, get_question, next_question_id,
)

SAMPLE = """\
sections:
  - id: 3.6-shuffle
    num: "3.6"
    title: Shuffle
    default_k: 18
questions:
  - id: 3.6-q01
    section: 3.6-shuffle
    text: "What triggers a shuffle?"
    version: "n/a"
    k: null
    status: answered
  - id: 3.6-q02
    section: 3.6-shuffle
    text: "Sort vs hash shuffle?"
    version: "3.5"
    k: 18
    status: pending
"""

def _write(tmp_path: Path) -> Path:
    p = tmp_path / "questions.yaml"
    p.write_text(SAMPLE, encoding="utf-8")
    return p

def test_load_parses_sections_and_questions(tmp_path):
    reg = load_registry(_write(tmp_path))
    assert reg.sections[0] == Section("3.6-shuffle", "3.6", "Shuffle", 18)
    assert reg.questions[1].k == 18
    assert reg.questions[0].k is None

def test_questions_in_preserves_order(tmp_path):
    reg = load_registry(_write(tmp_path))
    assert [q.id for q in questions_in(reg, "3.6-shuffle")] == ["3.6-q01", "3.6-q02"]

def test_get_question_raises_on_missing(tmp_path):
    reg = load_registry(_write(tmp_path))
    with pytest.raises(KeyError):
        get_question(reg, "9.9-q99")

def test_next_id_increments(tmp_path):
    reg = load_registry(_write(tmp_path))
    assert next_question_id(reg, "3.6-shuffle") == "3.6-q03"

def test_next_id_first_when_empty(tmp_path):
    reg = Registry(sections=[Section("1.1-x", "1.1", "X", 15)], questions=[])
    assert next_question_id(reg, "1.1-x") == "1.1-q01"

def test_save_load_roundtrip_preserves_k_null(tmp_path):
    reg = load_registry(_write(tmp_path))
    out = tmp_path / "out.yaml"
    save_registry(reg, out)
    assert "k: null" in out.read_text(encoding="utf-8")
    assert load_registry(out).questions[0].k is None

def test_load_raises_on_unknown_section(tmp_path):
    yaml_text = """\
sections:
  - id: 3.6-shuffle
    num: "3.6"
    title: Shuffle
    default_k: 18
questions:
  - id: 3.6-q01
    section: 9.9-unknown
    text: "What triggers a shuffle?"
    version: "n/a"
    k: null
    status: answered
"""
    p = tmp_path / "questions.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(ValueError, match="unknown section"):
        load_registry(p)

def test_load_raises_on_invalid_status(tmp_path):
    yaml_text = """\
sections:
  - id: 3.6-shuffle
    num: "3.6"
    title: Shuffle
    default_k: 18
questions:
  - id: 3.6-q01
    section: 3.6-shuffle
    text: "What triggers a shuffle?"
    version: "n/a"
    k: null
    status: bogus
"""
    p = tmp_path / "questions.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(ValueError, match="invalid status"):
        load_registry(p)

def test_load_raises_on_invalid_version(tmp_path):
    yaml_text = """\
sections:
  - id: 3.6-shuffle
    num: "3.6"
    title: Shuffle
    default_k: 18
questions:
  - id: 3.6-q01
    section: 3.6-shuffle
    text: "What triggers a shuffle?"
    version: "9.9"
    k: null
    status: answered
"""
    p = tmp_path / "questions.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(ValueError, match="invalid version"):
        load_registry(p)
