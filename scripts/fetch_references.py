"""Fetch and convert all sources listed in references/index.yaml.

Usage: uv run scripts/fetch_references.py
"""

import re
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

# requests/trafilatura/rich are imported lazily inside the functions that need
# them (the live network-fetch functions, and main()'s console/table output),
# so that `from scripts.fetch_references import main` works in a minimal dev
# env where the `research` group isn't installed — mirrors scripts/ask.py.

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO_ROOT / "references" / "index.yaml"
JIRA_KEY_RE = re.compile(r"/browse/([A-Z]+-\d+)")
JIRA_ATTACHMENT_EXTS = (".docx", ".doc", ".pdf")


def html_to_markdown(html: str) -> str:
    """Convert a JIRA description/comment HTML snippet to markdown via pandoc."""
    if not html:
        return ""
    result = subprocess.run(
        ["pandoc", "-f", "html", "-t", "markdown"],
        input=html,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def fetch_web(source: dict) -> tuple[str, int]:
    """Fetch an article page: trafilatura first, fall back to lynx -dump."""
    import trafilatura

    url = source["url"]
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded) if downloaded else None
    if text and len(text.encode("utf-8")) >= source["min_bytes"]:
        return text, len(text.encode("utf-8"))

    result = subprocess.run(
        ["lynx", "-dump", "-nolist", url],
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = result.stdout
    return text, len(text.encode("utf-8"))


def fetch_source(source: dict) -> tuple[str, int]:
    """Fetch a raw source file verbatim (e.g. Scala from raw.githubusercontent.com)."""
    import requests

    resp = requests.get(source["url"], timeout=60)
    resp.raise_for_status()
    return resp.text, len(resp.content)


def fetch_paper(source: dict) -> tuple[str, int]:
    """Download a PDF and convert with pdftotext -layout."""
    import requests

    tmp_pdf = REPO_ROOT / "references" / "papers" / f"{source['id']}.pdf"
    resp = requests.get(source["url"], timeout=120)
    resp.raise_for_status()
    tmp_pdf.write_bytes(resp.content)

    result = subprocess.run(
        ["pdftotext", "-layout", str(tmp_pdf), "-"],
        capture_output=True,
        text=True,
    )
    tmp_pdf.unlink()
    return result.stdout, len(result.stdout.encode("utf-8"))


def fetch_jira(source: dict) -> tuple[str, int]:
    """Fetch a ticket via JIRA's XML export view and pull in any doc/pdf attachments.

    The REST API (rest/api/2/issue/<KEY>) doesn't expose the `attachment` field on
    Apache's JIRA instance, but the issue-xml export view does — so that's used
    instead of the REST API for both metadata and attachment discovery.
    """
    import requests

    match = JIRA_KEY_RE.search(source["url"])
    if not match:
        raise ValueError(f"could not extract JIRA key from url: {source['url']}")
    key = match.group(1)

    xml_url = f"https://issues.apache.org/jira/si/jira.issueviews:issue-xml/{key}/{key}.xml"
    resp = requests.get(xml_url, timeout=60)
    resp.raise_for_status()
    item = ET.fromstring(resp.text).find(".//item")

    summary = item.findtext("summary") or ""
    description = item.findtext("description") or ""

    lines = [f"# {key}: {summary}", "", "## Description", "", html_to_markdown(description), ""]

    comments = item.findall("./comments/comment")
    if comments:
        lines.append("## Comments")
        for comment in comments:
            lines.append(f"### {comment.get('author')}")
            lines.append(html_to_markdown(comment.text or ""))
            lines.append("")

    attachments = item.findall("./attachments/attachment")
    for attachment in attachments:
        filename = attachment.get("name")
        suffix = Path(filename).suffix.lower()
        if suffix not in JIRA_ATTACHMENT_EXTS:
            continue

        att_url = f"https://issues.apache.org/jira/secure/attachment/{attachment.get('id')}/{urllib.parse.quote(filename)}"
        att_resp = requests.get(att_url, timeout=60)
        att_resp.raise_for_status()
        tmp_path = REPO_ROOT / "references" / f"_tmp_{key}{suffix}"
        tmp_path.write_bytes(att_resp.content)

        try:
            if suffix in (".docx", ".doc"):
                result = subprocess.run(
                    ["pandoc", "-f", "docx" if suffix == ".docx" else "doc", "-t", "markdown", str(tmp_path)],
                    capture_output=True,
                    text=True,
                )
                converted = result.stdout
            else:  # .pdf
                result = subprocess.run(
                    ["pdftotext", "-layout", str(tmp_path), "-"],
                    capture_output=True,
                    text=True,
                )
                converted = result.stdout
        finally:
            tmp_path.unlink()

        lines.append(f"## Attachment: {filename}")
        lines.append(converted)
        lines.append("")

    text = "\n".join(lines)
    return text, len(text.encode("utf-8"))


def main() -> int:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    index = yaml.safe_load(INDEX_PATH.read_text())
    sources = index["sources"]

    rows = []
    any_failed = False

    for source in sources:
        sid = source["id"]
        stype = source["type"]

        if stype == "book":
            local = source.get("local")
            console.print(
                f"[yellow]reminder:[/yellow] '{sid}' is type=book — "
                f"acquire manually and place at the target path"
            )
            rows.append((sid, "skipped", "-", source["version_bucket"]))
            continue

        local_path = REPO_ROOT / source["local"]
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if stype == "web":
                text, nbytes = fetch_web(source)
            elif stype == "source":
                text, nbytes = fetch_source(source)
            elif stype == "paper":
                text, nbytes = fetch_paper(source)
            elif stype == "jira":
                text, nbytes = fetch_jira(source)
            else:
                raise ValueError(f"unknown source type: {stype}")

            local_path.write_text(text, encoding="utf-8")

            if nbytes < source["min_bytes"]:
                status = "thin"
            else:
                status = "ok"

        except Exception as exc:
            status = "failed"
            nbytes = 0
            console.print(f"[red]error[/red] fetching {sid}: {exc}")
            any_failed = True

        if status in ("failed", "thin"):
            any_failed = True

        rows.append((sid, status, str(nbytes), source["version_bucket"]))

    table = Table(title="fetch_references.py summary")
    table.add_column("source id")
    table.add_column("status")
    table.add_column("bytes")
    table.add_column("version bucket")
    for row in rows:
        style = {"ok": "green", "failed": "red", "thin": "yellow", "skipped": "dim"}.get(row[1], "")
        table.add_row(*row, style=style)
    console.print(table)

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
