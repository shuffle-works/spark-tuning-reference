"""Content gate: manifest-mapping validation (fatal) and content-staleness
reporting (advisory banner, non-fatal).

Originally split out so the (now-retired) Node site build could shell out to
it without duplicating this logic in JS. HTML rendering has since moved
upstream entirely — this repo's responsibility ends at maintaining
content/*.md — so this script now runs standalone in CI (see
.github/workflows/ci.yml) rather than as a build prerequisite.

Run: uv run scripts/prebuild_checks.py --corpus spark
Exit 0 and print the staleness banner even when pages are stale (advisory);
exit 1 only on a manifest-mapping error (fatal).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_manifest_mapping import collect_errors  # noqa: E402
from scripts.content_state import report as content_report, load_state  # noqa: E402
from scripts.corpus import CORPORA  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=list(CORPORA), default="spark")
    args = parser.parse_args()
    corpus = CORPORA[args.corpus]

    mapping_errors = collect_errors(corpus.manifest_path, corpus.answers_dir)
    if mapping_errors:
        print("manifest mapping error(s):", file=sys.stderr)
        print("\n".join(mapping_errors), file=sys.stderr)
        sys.exit(1)

    import yaml

    manifest = yaml.safe_load(corpus.manifest_path.read_text(encoding="utf-8"))
    statuses = content_report(manifest, load_state(corpus.content_state_path), REPO_ROOT)
    stale = {p: s for p, s in statuses.items() if s != "ok"}
    if stale:
        print("warning: content pages out of sync with their section answers:", file=sys.stderr)
        for page, status in sorted(stale.items()):
            print(f"  {status}: {page}", file=sys.stderr)
    else:
        print("content pages: all up to date")


if __name__ == "__main__":
    main()
