"""Root router package init allowing python -m router execution."""

import sys
from pathlib import Path

# Ensure src path is in sys.path
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.insert(0, src_path)
