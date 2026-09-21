"""Report-only citation link-checker.

Collects every `[^id]` footnote id cited across both corpora's answer files,
maps each to its source URL in the corpus index.yaml, and GETs the URL to
verify it still resolves. Flags dead links (non-200) and sources that now
redirect to their homepage (a common sign the deep link rotted away).

Scheduled / report-only: NEVER wire this into a PR gate. Exits non-zero only
on HARD failures (non-200 or homepage redirect) so a weekly cron can open a
tracking issue. Network errors are reported SEPARATELY as soft "unverified".
Stdlib-only network (urllib) so it needs no extra dependency.
"""
from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen  # noqa: F401  (urlopen patched in tests)

import yaml

# Runnable as a file (CI does `uv run scripts/check_citations.py`), not only as
# a module under pytest — bootstrap the repo root so `scripts.*` imports resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.corpus import CORPORA  # noqa: E402  (needs the sys.path bootstrap above)

# A real browser UA — some hosts 403 the default urllib agent.
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 15  # seconds per request
MAX_WORKERS = 6  # per-run concurrency cap — polite, avoids hammering hosts

# Hosts known to block bots with 4xx/429 despite the link being fine.
# A non-200 from these is downgraded to "unverified" instead of a hard fail.
ALLOWLIST_HOSTS = frozenset({
    "www.oreilly.com",
    "learning.oreilly.com",
    "dl.acm.org",
    "ieeexplore.ieee.org",
})

_CITE_RE = re.compile(r"\[\^([^\]]+)\]")


def collect_cited_ids(answers_dir: Path) -> set[str]:
    """Every `[^id]` footnote id cited across `answers_dir/**/*.md`."""
    ids: set[str] = set()
    for md in Path(answers_dir).glob("**/*.md"):
        ids.update(_CITE_RE.findall(md.read_text(encoding="utf-8")))
    return ids


def load_id_urls(index_path: Path) -> dict[str, str]:
    """source_id -> url, keeping only sources with a non-null url."""
    index = yaml.safe_load(Path(index_path).read_text(encoding="utf-8"))
    return {s["id"]: s["url"] for s in index["sources"] if s.get("url")}


def is_homepage_redirect(original: str, final: str) -> bool:
    """True when a deep link on some host now lands on that host's root.

    Same host + original had a real path + final path is '/' or empty. A host
    change is NOT this heuristic (returns False) — that's a legitimate move.
    """
    o, f = urlsplit(original), urlsplit(final)
    if o.netloc != f.netloc:
        return False
    return bool(o.path.strip("/")) and not f.path.strip("/")


@dataclass
class Result:
    source_id: str
    url: str
    kind: str  # "ok" | "fail" | "unverified"
    detail: str


def _classify(source_id: str, url: str, status: int, final: str) -> Result:
    """Shared outcome classification for both the 200 and HTTPError paths.

    A non-200 status is a hard fail, unless the host is on ALLOWLIST_HOSTS
    (known to block bots) — those are downgraded to soft "unverified".
    """
    if status != 200:
        host = urlsplit(url).netloc
        kind = "unverified" if host in ALLOWLIST_HOSTS else "fail"
        return Result(source_id, url, kind, f"HTTP {status}")
    if is_homepage_redirect(url, final):
        return Result(source_id, url, "fail", f"redirected to homepage: {final}")
    return Result(source_id, url, "ok", "")


def check_url(source_id: str, url: str) -> Result:
    """GET the URL, following redirects; classify the outcome."""
    req = Request(url, headers={"User-Agent": BROWSER_UA})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            final = resp.geturl()
    except HTTPError as exc:  # any non-2xx status — classify like the 200 path
        return _classify(source_id, url, exc.code, exc.geturl() or url)
    except (URLError, TimeoutError, OSError) as exc:  # connection/timeout = soft
        return Result(source_id, url, "unverified", f"error: {exc}")

    return _classify(source_id, url, status, final)


def gather_targets() -> dict[str, str]:
    """Cited-and-mappable url -> source_id, deduped across both corpora."""
    targets: dict[str, str] = {}
    for corpus in CORPORA.values():
        id_urls = load_id_urls(corpus.index_path)
        for cid in collect_cited_ids(corpus.answers_dir):
            url = id_urls.get(cid)
            if url and url not in targets:
                targets[url] = cid
    return targets


def _print_summary(results: list[Result]) -> None:
    order = {"fail": 0, "unverified": 1, "ok": 2}
    results = sorted(results, key=lambda r: (order[r.kind], r.source_id))
    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(title="Citation link check")
        table.add_column("status")
        table.add_column("source id")
        table.add_column("detail / url", overflow="fold")
        style = {"fail": "red", "unverified": "yellow", "ok": "green"}
        for r in results:
            table.add_row(f"[{style[r.kind]}]{r.kind}[/]", r.source_id, r.detail or r.url)
        Console().print(table)
    except ImportError:
        for r in results:
            print(f"{r.kind:11} {r.source_id:28} {r.detail or r.url}")


def main() -> int:
    targets = gather_targets()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(lambda kv: check_url(kv[1], kv[0]), targets.items()))

    _print_summary(results)

    fails = [r for r in results if r.kind == "fail"]
    unverified = [r for r in results if r.kind == "unverified"]
    print(
        f"\n{len(results)} checked | {len(fails)} failed | "
        f"{len(unverified)} unverified | "
        f"{sum(r.kind == 'ok' for r in results)} ok"
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
