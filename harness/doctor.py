"""Module entrypoint for python -m harness.doctor."""
import sys
from pathlib import Path

# Ensure repo root is in sys.path
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.harness_doctor import *  # noqa: F401, F403
from scripts.harness_doctor import main

if __name__ == "__main__":
    main()
