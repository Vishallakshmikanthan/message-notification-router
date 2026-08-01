"""Script to generate submission code.zip package.

Implements Packaging Cleanliness Protocol from submission_strategy.md §4.2:
- Excludes: .git/, __pycache__/, .pytest_cache/, .venv/, .env, *.pyc
- Includes: src/, docs/, tests/, eval/, pyproject.toml, README.md, markdown docs

Spec: submission_strategy.md §4.2.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", ".mypy_cache", ".ruff_cache", "submission"}
EXCLUDED_EXTENSIONS = {".pyc", ".pyo", ".env", ".zip"}


def create_code_zip(
    output_zip_path: str = "submission/code.zip",
    project_root: str = ".",
) -> None:
    """Pack clean codebase into zip archive."""
    root = Path(project_root).resolve()
    out_p = Path(output_zip_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    print(f"Creating submission archive at {out_p}...")
    zipped_count = 0

    with zipfile.ZipFile(out_p, "w", zipfile.ZIP_DEFLATED) as zipf:
        for path in root.rglob("*"):
            if path.is_dir():
                continue

            # Check directory exclusions
            rel_parts = path.relative_to(root).parts
            if any(part in EXCLUDED_DIRS for part in rel_parts):
                continue

            # Check extension exclusions
            if path.suffix in EXCLUDED_EXTENSIONS:
                continue

            arcname = path.relative_to(root)
            zipf.write(path, arcname=arcname)
            zipped_count += 1

    print(f"Successfully packaged {zipped_count} files into {out_p}")


if __name__ == "__main__":
    create_code_zip()
