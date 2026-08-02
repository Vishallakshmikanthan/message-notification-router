"""Hackerrank execution wrapper script."""

import os
import sys
from pathlib import Path

code_dir = Path(__file__).resolve().parent
repo_root = code_dir.parent.parent
src_dir = repo_root / "src"

for path in (str(src_dir), str(repo_root)):
    if path not in sys.path:
        sys.path.insert(0, path)

from router.__main__ import main

if __name__ == "__main__":
    main()
