"""Deterministic, no-LLM lint for AI writing tells and Humanize-stage invariants.

Encodes the literal rules from the `writing-prose-like-a-human` skill/agent
(banned vocabulary, structural tics, em dash / curly quote bans) plus this
project's own hard constraints on what the Humanize stage must never change
(footnotes, `## Sources` block, `[UNRESOURCED]`/`[NEEDS-REVIEW]` markers, the
`## <question>` heading). It is advisory support for that LLM pass, not a
replacement for it.

Usage:
  uv run python -m scripts.check_prose <file_or_dir> ...    # vocabulary/structural lint
  uv run python -m scripts.check_prose --diff BEFORE AFTER  # invariant check around Humanize
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Literal "Avoid" entries from the writing-prose-like-a-human skill/agent tables.
# NOTE: bare "key" is deliberately omitted — this corpus uses it constantly as a
# domain noun (partition key, shuffle key, join key), not as the inflation
# adjective the skill targets. Everything else is matched literally, so
# occasional false positives on legitimate technical usage (e.g. "leverage
# broadcast joins") are expected; review flags, don't treat them as hard fails.
BANNED_PHRASES: dict[str, list[str]] = {
    "significance_inflation": [
        "pivotal", "crucial", "vital", "testament", "watershed moment",
        "indelible mark", "deeply rooted", "lasting legacy", "enduring legacy",
        "broader movement", "evolving landscape", "focal point",
        "groundbreaking", "captivate", "plays a significant role",
        "key turning point", "marks a shift", "represents a shift",
        "contributing to the",
    ],
    "plain_verbs": [
        "serves as", "stands as", "showcases", "showcase", "underscores",
        "underscore", "boasts", "boast", "leverages", "leverage",
        "encompasses", "encompass", "facilitates", "facilitate", "utilizes",
        "utilize", "demonstrates", "delves into", "delve into", "ensures",
        "highlights", "highlight", "exemplifies", "exemplify", "cultivates",
        "cultivate", "represents",
    ],
    "false_sophistication": [
        "intricate", "interplay", "garner", "align with", "resonate with",
        "vibrant", "enhance", "nestled", "in the heart of", "navigate",
        "orchestrate", "paradigm", "robust", "seamless", "meticulous",
        "multifaceted", "bespoke", "instrumental", "intricacies", "renowned",
        "cutting-edge", "state-of-the-art", "holistic", "synergistic",
        "innovative",
    ],
    "structural_tics": [
        "additionally,", "furthermore,", "moreover,", "it is worth noting",
        "it's worth noting", "it's important to remember",
        "it's important to note", "despite these challenges",
        "reflects broader", "setting the stage for",
        "in today's fast-paced world", "in the realm of", "in the world of",
        "at its core", "a delicate balance",
        "while specific details are limited", "based on available information",
        "in summary", "in conclusion", "overall,",
    ],
    "vague_attribution": [
        "industry reports suggest", "experts argue", "critics argue",
        "several sources", "several publications",
        "active social media presence", "independent coverage",
    ],
}

CURLY_CHARS = "‘’“”…"  # ' ' " " …
EM_DASH = "—"
EM_DASH_MAX = 0

CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
SOURCES_SECTION_RE = re.compile(r"^## Sources\s*$.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
HEADING_RE = re.compile(r"^## (?!Sources\s*$).+$", re.MULTILINE)
HEADING_LINE_RE = re.compile(r"^#{1,6} .*$", re.MULTILINE)
FOOTNOTE_DEF_LINE_RE = re.compile(r"^\[\^[^\]]+\]:.*$", re.MULTILINE)
GAP_MARKER_RE = re.compile(r"\[(?:UNRESOURCED|NEEDS-REVIEW)[^\]]*\]", re.DOTALL)
FOOTNOTE_TOKEN_RE = re.compile(r"\[\^[^\]]+\]")
NUMBER_RE = re.compile(r"\b\d[\d,.]*\b")


def _blank_span(match: re.Match) -> str:
    return "\n" * match.group(0).count("\n")


def mask_for_lint(text: str) -> str:
    """Blank out everything the Humanize hard constraints forbid touching, so the
    lint only ever scores prose the humanizer is actually allowed to rewrite:
    fenced code, front matter, the Sources section, any heading line, footnote
    definition lines (even without a `## Sources` heading, e.g. content pages),
    and [UNRESOURCED]/[NEEDS-REVIEW] marker spans. Line count is preserved.
    """
    text = FRONT_MATTER_RE.sub(_blank_span, text)
    text = SOURCES_SECTION_RE.sub(_blank_span, text)
    text = HEADING_LINE_RE.sub("", text)
    text = FOOTNOTE_DEF_LINE_RE.sub("", text)
    text = GAP_MARKER_RE.sub(_blank_span, text)
    lines = text.split("\n")
    out, in_fence = [], False
    for line in lines:
        if CODE_FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
        elif in_fence:
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def lint_text(text: str) -> list[str]:
    errors: list[str] = []
    masked = mask_for_lint(text)
    lines = masked.split("\n")

    for lineno, line in enumerate(lines, start=1):
        low = line.lower()
        for category, phrases in BANNED_PHRASES.items():
            for phrase in phrases:
                if phrase.lower() in low:
                    errors.append(f"{lineno}: [{category}] banned phrase: {phrase!r}")

    em_dash_count = masked.count(EM_DASH)
    if em_dash_count > EM_DASH_MAX:
        errors.append(f"em dash count {em_dash_count} exceeds max {EM_DASH_MAX}")

    for ch in CURLY_CHARS:
        if ch in masked:
            errors.append(f"curly quote/ellipsis character found: {ch!r} (use straight equivalent)")
            break

    not_only_count = len(re.findall(r"\bnot only\b.*?\bbut\b", masked, re.IGNORECASE | re.DOTALL))
    if not_only_count > 1:
        errors.append(f"'not only ... but' used {not_only_count} times (max 1 per doc)")

    return errors


def lint_paths(paths: list[Path]) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for path in paths:
        files = sorted(path.rglob("*.md")) if path.is_dir() else [path]
        for f in files:
            issues = lint_text(f.read_text(encoding="utf-8"))
            if issues:
                results[str(f)] = issues
    return results


def extract_invariants(text: str) -> dict:
    sources_match = SOURCES_SECTION_RE.search(text)
    heading_match = HEADING_RE.search(text)
    body_wo_sources = SOURCES_SECTION_RE.sub("", text)
    return {
        "footnote_tokens": sorted(FOOTNOTE_TOKEN_RE.findall(text)),
        "sources_block": sources_match.group(0).strip() if sources_match else None,
        "unresourced_count": text.count("[UNRESOURCED]"),
        "needs_review_count": len(re.findall(r"\[NEEDS-REVIEW", text)),
        "heading": heading_match.group(0).strip() if heading_match else None,
        "numbers": sorted(NUMBER_RE.findall(body_wo_sources)),
    }


def diff_invariants(before: str, after: str) -> list[str]:
    b, a = extract_invariants(before), extract_invariants(after)
    errors: list[str] = []
    if b["footnote_tokens"] != a["footnote_tokens"]:
        errors.append(f"footnote tokens changed: {b['footnote_tokens']} -> {a['footnote_tokens']}")
    if b["sources_block"] != a["sources_block"]:
        errors.append("## Sources block changed")
    if b["unresourced_count"] != a["unresourced_count"]:
        errors.append(f"[UNRESOURCED] count changed: {b['unresourced_count']} -> {a['unresourced_count']}")
    if b["needs_review_count"] != a["needs_review_count"]:
        errors.append(f"[NEEDS-REVIEW] count changed: {b['needs_review_count']} -> {a['needs_review_count']}")
    if b["heading"] != a["heading"]:
        errors.append(f"heading changed: {b['heading']!r} -> {a['heading']!r}")
    if b["numbers"] != a["numbers"]:
        errors.append(f"numeric tokens changed: {b['numbers']} -> {a['numbers']}")
    return errors


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="*", type=Path)
    p.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    args = p.parse_args(argv)

    if args.diff:
        before_path, after_path = (Path(x) for x in args.diff)
        errors = diff_invariants(
            before_path.read_text(encoding="utf-8"), after_path.read_text(encoding="utf-8")
        )
        if errors:
            print(f"invariant check failed: {after_path}")
            print("\n".join(f"  {e}" for e in errors))
            return 1
        print(f"OK: invariants preserved ({after_path})")
        return 0

    if not args.paths:
        p.error("give one or more files/dirs to lint, or use --diff BEFORE AFTER")

    results = lint_paths(args.paths)
    if results:
        for f, issues in results.items():
            print(f"{f}:")
            for issue in issues:
                print(f"  {issue}")
        total = sum(len(v) for v in results.values())
        print(f"\n{total} prose issue(s) in {len(results)} file(s).")
        return 1
    print("OK: no prose issues found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
