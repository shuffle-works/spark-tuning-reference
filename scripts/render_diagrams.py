# /// script
# requires-python = ">=3.11"
# dependencies = ["mermaidx==0.9.5"]
# ///
"""Offline Mermaid -> SVG renderer for the tuning-reference diagrams.

Reads every content/diagrams/*.mmd source and writes two committed SVGs per
diagram: <name>.svg (light) and <name>.dark.svg (dark). Content pages link both
as a light-only/dark-only <img> pair, so the upstream renderer's own theme
toggle can pick the right one instead of only tracking the OS preference.

Colours come from the sparkforensics doc palette (docs-site/.vitepress/theme/
custom.css) so the diagrams read as part of the same site. The .mmd sources carry
structure and labels only, never colours: the palette lives here, in one place,
for both themes.

Rendering uses mermaidx, which runs the real mermaid.js in an embedded JS engine
(QuickJS) - no Node, no npm, no browser, no system binary. The dependency is
declared inline (PEP 723) and provisioned by uv only when this script runs, so it
never enters the project's own dependency tree.

Run: uv run scripts/render_diagrams.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# mermaidx is declared via inline PEP 723 metadata above, not in the project's
# own dependency tree (see module docstring), so it's imported lazily inside
# render_one() — that keeps `from scripts.render_diagrams import main` working
# in a plain dev env, where main()'s glob/dispatch/error-handling is testable
# with render_one() mocked out.
DIAGRAMS_DIR = Path(__file__).resolve().parent.parent / "content" / "diagrams"

FONT = "Recursive, ui-sans-serif, system-ui, -apple-system, sans-serif"

# Mermaid `base` theme variables mapped to the doc palette, light and dark.
LIGHT = {
    "background": "transparent",
    "fontFamily": FONT,
    "primaryColor": "#ffffff",
    "primaryTextColor": "#151b1e",
    "primaryBorderColor": "#9aa8a3",
    "secondaryColor": "#f2f5f9",
    "tertiaryColor": "#eef1f6",
    "lineColor": "#4f5f60",
    "textColor": "#151b1e",
    "mainBkg": "#ffffff",
    "nodeBorder": "#9aa8a3",
    "nodeTextColor": "#151b1e",
    "clusterBkg": "#f2f5f9",
    "clusterBorder": "#dbe2df",
    "titleColor": "#151b1e",
    "edgeLabelBackground": "#eef1f6",
}

DARK = {
    "background": "transparent",
    "fontFamily": FONT,
    "primaryColor": "#17202c",
    "primaryTextColor": "#f4f4f5",
    "primaryBorderColor": "#3a4a52",
    "secondaryColor": "#11171a",
    "tertiaryColor": "#1a232f",
    "lineColor": "#a9b5b4",
    "textColor": "#f4f4f5",
    "mainBkg": "#17202c",
    "nodeBorder": "#3a4a52",
    "nodeTextColor": "#f4f4f5",
    "clusterBkg": "#11171a",
    "clusterBorder": "#233035",
    "titleColor": "#f4f4f5",
    "edgeLabelBackground": "#11171a",
}

# (output suffix, theme variables) for the two committed variants.
PASSES = [(".svg", LIGHT), (".dark.svg", DARK)]


def render_one(source: str, theme_variables: dict) -> str:
    import mermaidx

    diagram = mermaidx.render(
        source,
        theme="base",
        config={
            "fontFamily": FONT,
            "themeVariables": theme_variables,
            # mermaidx approximates text width from a bundled font table rather
            # than measuring in a browser, so it under-sizes nodes and force-wraps
            # long single tokens (e.g. config names) mid-word. A generous
            # wrappingWidth keeps those tokens on one line; genuine sentences
            # still wrap. Flowchart-only; state diagrams here have no long tokens.
            "flowchart": {"wrappingWidth": 400},
        },
    )
    return diagram.svg()


def main() -> int:
    sources = sorted(DIAGRAMS_DIR.glob("*.mmd"))
    if not sources:
        print("No .mmd sources in content/diagrams/.")
        return 0

    failures = 0
    for mmd in sources:
        text = mmd.read_text(encoding="utf-8")
        for suffix, theme_variables in PASSES:
            out = mmd.with_name(mmd.stem + suffix)
            try:
                out.write_text(render_one(text, theme_variables), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 - report and keep going
                failures += 1
                print(f"FAIL {out.name}: {type(exc).__name__}: {exc}", file=sys.stderr)

    if failures:
        print(f"\n{failures} diagram render(s) failed.", file=sys.stderr)
        return 1
    print(f"Rendered {len(sources)} diagram(s) x2 themes into {DIAGRAMS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
