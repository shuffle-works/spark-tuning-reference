from scripts.content_state import page_hash, report, accept

def _manifest():
    return {"groups": [{"title": "G", "entries": [
        {"file": "content/a.md", "anchor": "a", "title": "A",
         "assembled_from": "research/answers/3.6-shuffle.md", "brief": "x"},
    ]}]}

def test_page_hash_stable(tmp_path):
    p = tmp_path / "proj.md"; p.write_text("hello", encoding="utf-8")
    assert page_hash(p) == page_hash(p)

def test_report_ungenerated_stale_ok(tmp_path):
    (tmp_path / "research/answers").mkdir(parents=True)
    proj = tmp_path / "research/answers/3.6-shuffle.md"
    proj.write_text("v1", encoding="utf-8")
    man = _manifest()

    assert report(man, {}, tmp_path) == {"content/a.md": "ungenerated"}

    state = {}
    accept(state, "content/a.md", page_hash(proj))
    assert report(man, state, tmp_path) == {"content/a.md": "ok"}

    proj.write_text("v2", encoding="utf-8")
    assert report(man, state, tmp_path) == {"content/a.md": "stale"}
