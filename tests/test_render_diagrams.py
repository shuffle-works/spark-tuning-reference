"""main()'s dispatch/error-handling over content/diagrams/*.mmd. render_one()
itself needs the real mermaidx (a PEP 723 inline dep never added to the
project's own dependency tree, see the module docstring) so it's mocked out
here rather than exercised for real.
"""
import scripts.render_diagrams as render_diagrams


def test_main_with_no_sources_prints_notice_and_returns_0(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(render_diagrams, "DIAGRAMS_DIR", tmp_path)
    assert render_diagrams.main() == 0
    assert "No .mmd sources" in capsys.readouterr().out


def test_main_renders_both_themes_per_source(tmp_path, monkeypatch):
    (tmp_path / "a.mmd").write_text("flowchart TD\nA-->B\n", encoding="utf-8")
    monkeypatch.setattr(render_diagrams, "DIAGRAMS_DIR", tmp_path)

    calls = []

    def fake_render_one(source, theme_variables):
        calls.append(theme_variables)
        return f"<svg theme={'dark' if theme_variables is render_diagrams.DARK else 'light'}/>"

    monkeypatch.setattr(render_diagrams, "render_one", fake_render_one)

    assert render_diagrams.main() == 0
    assert calls == [render_diagrams.LIGHT, render_diagrams.DARK]
    assert (tmp_path / "a.svg").read_text() == "<svg theme=light/>"
    assert (tmp_path / "a.dark.svg").read_text() == "<svg theme=dark/>"


def test_main_counts_failures_and_returns_1_but_keeps_going(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.mmd").write_text("flowchart TD\nA-->B\n", encoding="utf-8")
    monkeypatch.setattr(render_diagrams, "DIAGRAMS_DIR", tmp_path)

    def failing_render_one(source, theme_variables):
        raise RuntimeError("bad diagram")

    monkeypatch.setattr(render_diagrams, "render_one", failing_render_one)

    rc = render_diagrams.main()

    assert rc == 1
    err = capsys.readouterr().err
    assert err.count("FAIL") == 2  # light + dark pass both fail, independently
    assert not (tmp_path / "a.svg").exists()


def test_main_one_theme_fails_other_succeeds(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.mmd").write_text("flowchart TD\nA-->B\n", encoding="utf-8")
    monkeypatch.setattr(render_diagrams, "DIAGRAMS_DIR", tmp_path)

    def flaky_render_one(source, theme_variables):
        if theme_variables is render_diagrams.DARK:
            raise RuntimeError("dark theme broke")
        return "<svg/>"

    monkeypatch.setattr(render_diagrams, "render_one", flaky_render_one)

    rc = render_diagrams.main()

    assert rc == 1
    assert (tmp_path / "a.svg").read_text() == "<svg/>"
    assert not (tmp_path / "a.dark.svg").exists()
