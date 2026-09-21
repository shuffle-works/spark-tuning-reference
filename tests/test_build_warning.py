import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_prebuild_checks_reports_content_staleness():
    r = subprocess.run(
        [sys.executable, "scripts/prebuild_checks.py", "--corpus", "spark"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    # warning banner text present in output (stdout+stderr) whether or not pages are stale
    assert "content pages" in (r.stdout + r.stderr).lower()
