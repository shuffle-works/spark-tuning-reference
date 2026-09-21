import sys
from pathlib import Path

# Add repo root to path so scripts module is importable
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
