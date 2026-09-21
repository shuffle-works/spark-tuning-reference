"""The CI staleness gate. `content_state.py --check` must exit
non-zero when any page is stale/ungenerated, zero when all are ok."""
import subprocess
import sys
from pathlib import Path

import yaml

from scripts.content_state import gate, load_state, report
from scripts.corpus import CORPORA

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_gate_exit_code_semantics():
    assert gate({}) == 0
    assert gate({"content/a.md": "ok"}) == 0
    assert gate({"content/a.md": "ok", "content/b.md": "stale"}) == 1
    assert gate({"content/a.md": "ungenerated"}) == 1


def test_check_cli_matches_report():
    """End-to-end: the --check CLI (run as a file, as CI invokes it) exits with
    the code the report implies — 0 iff every page is ok."""
    corpus = CORPORA["spark"]
    manifest = yaml.safe_load(corpus.manifest_path.read_text(encoding="utf-8"))
    expected = gate(report(manifest, load_state(corpus.content_state_path), REPO_ROOT))

    proc = subprocess.run(
        [sys.executable, "scripts/content_state.py", "--check"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == expected, proc.stderr
    assert proc.returncode in (0, 1)
