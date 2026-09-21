# tests/test_add_question.py
from scripts.registry import Registry, Section, Question
from scripts.add_question import add_question

def _reg():
    return Registry(
        sections=[Section("3.6-shuffle", "3.6", "Shuffle", 18)],
        questions=[Question("3.6-q01", "3.6-shuffle", "Old?", "n/a", None, "answered")],
    )

def test_add_appends_pending_with_new_id():
    reg = _reg()
    qid = add_question(reg, "New question?", "3.6-shuffle", "3.5", 20)
    assert qid == "3.6-q02"
    added = reg.questions[-1]
    assert (added.text, added.version, added.k, added.status) == ("New question?", "3.5", 20, "pending")

def test_add_does_not_mutate_existing():
    reg = _reg()
    before = Question("3.6-q01", "3.6-shuffle", "Old?", "n/a", None, "answered")
    add_question(reg, "Another?", "3.6-shuffle", "n/a", None)
    assert reg.questions[0] == before
