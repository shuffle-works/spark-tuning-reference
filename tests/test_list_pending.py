from scripts.registry import Registry, Section, Question
from scripts.list_pending import pending_ids


def test_pending_ids_in_order():
    reg = Registry(
        sections=[Section("3.6-shuffle", "3.6", "Shuffle", 18)],
        questions=[
            Question("3.6-q01", "3.6-shuffle", "A?", "n/a", None, "answered"),
            Question("3.6-q02", "3.6-shuffle", "B?", "n/a", None, "pending"),
            Question("3.6-q03", "3.6-shuffle", "C?", "n/a", None, "pending"),
        ],
    )
    assert pending_ids(reg) == ["3.6-q02", "3.6-q03"]
