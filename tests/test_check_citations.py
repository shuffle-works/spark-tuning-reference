import io
from email.message import Message
from urllib.error import HTTPError, URLError

import scripts.check_citations as cc
from scripts.check_citations import check_url, collect_cited_ids, is_homepage_redirect


def _http_error(url: str, code: int) -> HTTPError:
    """A real HTTPError whose .code / .geturl() work (needs a non-None fp)."""
    return HTTPError(url, code, "err", Message(), io.BytesIO(b""))


class _FakeResp:
    """Minimal stand-in for a urlopen() context manager on the 200 path."""

    def __init__(self, status: int, final: str):
        self._status = status
        self._final = final

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def getcode(self):
        return self._status

    def geturl(self):
        return self._final


def test_collect_cited_ids_from_nested_tree(tmp_path):
    answers = tmp_path / "answers"
    (answers / "q").mkdir(parents=True)
    # top-level file, two distinct ids, one repeated
    (answers / "3.1-intro.md").write_text(
        "Text[^learning-spark-2e] and more[^definitive-guide], again[^learning-spark-2e].\n",
        encoding="utf-8",
    )
    # nested per-question file, new id
    (answers / "q" / "3.1-q01.md").write_text(
        "A claim[^spark-configuration].\n", encoding="utf-8"
    )
    # a non-md file must be ignored
    (answers / "notes.txt").write_text("[^should-not-count]\n", encoding="utf-8")

    assert collect_cited_ids(answers) == {
        "learning-spark-2e",
        "definitive-guide",
        "spark-configuration",
    }


def test_homepage_redirect_same_host_path_to_root_is_flagged():
    assert is_homepage_redirect(
        "https://example.com/docs/tuning.html", "https://example.com/"
    )
    # empty final path (bare host) also counts as homepage
    assert is_homepage_redirect(
        "https://example.com/docs/tuning.html", "https://example.com"
    )


def test_homepage_redirect_preserved_path_is_ok():
    # same host, real path preserved (e.g. http->https) => not a homepage redirect
    assert not is_homepage_redirect(
        "http://example.com/docs/tuning.html", "https://example.com/docs/tuning.html"
    )


def test_homepage_redirect_different_host_is_ok():
    # host changed entirely => not this heuristic, even if final path is '/'
    assert not is_homepage_redirect(
        "https://example.com/docs/tuning.html", "https://cdn.other.com/"
    )


def test_check_url_200_is_ok(monkeypatch):
    url = "https://example.com/docs/tuning.html"
    monkeypatch.setattr(cc, "urlopen", lambda *a, **k: _FakeResp(200, url))
    assert check_url("sid", url).kind == "ok"


def test_check_url_http_404_is_hard_fail(monkeypatch):
    url = "https://example.com/docs/gone.html"

    def raise_404(*_a, **_k):
        raise _http_error(url, 404)

    monkeypatch.setattr(cc, "urlopen", raise_404)
    assert check_url("sid", url).kind == "fail"


def test_check_url_http_403_from_allowlist_host_is_unverified(monkeypatch):
    # oreilly is on ALLOWLIST_HOSTS: a bot-block 4xx downgrades to soft unverified
    url = "https://www.oreilly.com/library/view/spark/9781492050032/"

    def raise_403(*_a, **_k):
        raise _http_error(url, 403)

    monkeypatch.setattr(cc, "urlopen", raise_403)
    assert check_url("sid", url).kind == "unverified"


def test_check_url_connection_error_is_unverified(monkeypatch):
    url = "https://example.com/docs/tuning.html"

    def raise_timeout(*_a, **_k):
        raise TimeoutError("timed out")

    monkeypatch.setattr(cc, "urlopen", raise_timeout)
    assert check_url("sid", url).kind == "unverified"

    def raise_urlerror(*_a, **_k):
        raise URLError("name resolution failed")

    monkeypatch.setattr(cc, "urlopen", raise_urlerror)
    assert check_url("sid", url).kind == "unverified"


def test_check_url_same_host_homepage_redirect_is_hard_fail(monkeypatch):
    url = "https://example.com/docs/tuning.html"
    # 200, but the deep link now lands on the host root => rotted deep link
    monkeypatch.setattr(cc, "urlopen", lambda *a, **k: _FakeResp(200, "https://example.com/"))
    assert check_url("sid", url).kind == "fail"
