"""Root CLI Entry Point for WhatsApp Message Notification Router."""

import os
import sys
from pathlib import Path

# Ensure 'src' and project root directory are in sys.path
root_dir = Path(__file__).resolve().parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from router.__main__ import main

if __name__ == "__main__":
    main()
