"""Load/validate/save the question registry (research/questions.yaml).

The registry is the single source of truth for research questions. Every other
artifact (per-question answers, section projections, content pages) derives from it.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

VALID_STATUS = ("pending", "answered", "needs-review")
VALID_VERSION = ("3.0", "3.5", "4.0", "n/a")


@dataclass
class Section:
    id: str
    num: str
    title: str
    default_k: int


@dataclass
class Question:
    id: str
    section: str
    text: str
    version: str
    k: int | None
    status: str


@dataclass
class Registry:
    sections: list[Section]
    questions: list[Question]


def load_registry(path: Path) -> Registry:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    sections = [Section(**s) for s in raw.get("sections", [])]
    section_ids = {s.id for s in sections}
    questions = []
    for q in raw.get("questions", []):
        question = Question(
            id=q["id"], section=q["section"], text=q["text"],
            version=q["version"], k=q.get("k"), status=q["status"],
        )
        if question.section not in section_ids:
            raise ValueError(f"question {question.id} references unknown section {question.section}")
        if question.status not in VALID_STATUS:
            raise ValueError(f"question {question.id} has invalid status {question.status}")
        if question.version not in VALID_VERSION:
            raise ValueError(f"question {question.id} has invalid version {question.version}")
        questions.append(question)
    return Registry(sections=sections, questions=questions)


def save_registry(reg: Registry, path: Path) -> None:
    data = {
        "sections": [
            {"id": s.id, "num": s.num, "title": s.title, "default_k": s.default_k}
            for s in reg.sections
        ],
        "questions": [
            {"id": q.id, "section": q.section, "text": q.text,
             "version": q.version, "k": q.k, "status": q.status}
            for q in reg.questions
        ],
    }
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
    Path(path).write_text(text, encoding="utf-8")


def questions_in(reg: Registry, section_id: str) -> list[Question]:
    return [q for q in reg.questions if q.section == section_id]


def get_question(reg: Registry, qid: str) -> Question:
    for q in reg.questions:
        if q.id == qid:
            return q
    raise KeyError(qid)


def next_question_id(reg: Registry, section_id: str) -> str:
    section = next(s for s in reg.sections if s.id == section_id)
    nums = [
        int(q.id.rsplit("-q", 1)[1])
        for q in reg.questions
        if q.section == section_id and "-q" in q.id
    ]
    return f"{section.num}-q{(max(nums) + 1 if nums else 1):02d}"
