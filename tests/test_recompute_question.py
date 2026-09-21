from scripts.registry import Registry, Section, Question
from scripts.recompute_question import recompute_question


def _reg():
    return Registry(
        sections=[Section("3.6-shuffle", "3.6", "Shuffle", 18)],
        questions=[
            Question("3.6-q01", "3.6-shuffle", "A?", "n/a", None, "answered"),
            Question("3.6-q02", "3.6-shuffle", "B?", "n/a", None, "answered"),
        ],
    )


def test_recompute_flips_only_target(tmp_path):
    reg = _reg()
    recompute_question(reg, "3.6-q02", tmp_path)
    assert reg.questions[0].status == "answered"
    assert reg.questions[1].status == "pending"


def test_recompute_backs_up_answer(tmp_path):
    (tmp_path / "3.6-q01.md").write_text("old answer\n", encoding="utf-8")
    reg = _reg()
    recompute_question(reg, "3.6-q01", tmp_path)
    assert (tmp_path / "3.6-q01.md.bak").read_text(encoding="utf-8") == "old answer\n"
    assert not (tmp_path / "3.6-q01.md").exists()
