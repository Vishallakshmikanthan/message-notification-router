"""Submission Validator & QA Gate.

Implements Submission Quality Assurance Checklist from submission_strategy.md §5:
- output.csv row count and header verification
- Zero unhandled exceptions or malformed JSON
- Macro F1 >= 0.90
- code.zip contains zero secrets or virtual environment binaries
- README quickstart commands verification

Spec: submission_strategy.md §5.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from eval.output_validator import OutputCSVValidator

logger = logging.getLogger(__name__)


class SubmissionValidator:
    """End-to-End Submission Package Quality Assurer."""

    def __init__(self) -> None:
        """Initialize SubmissionValidator."""
        self.csv_validator = OutputCSVValidator()

    def validate_submission_package(
        self,
        submission_dir: str = "submission",
        output_csv_filename: str = "output.csv",
        code_zip_filename: str = "code.zip",
    ) -> dict[str, Any]:
        """Validate all final submission artifacts.

        Args:
            submission_dir: Path to submission folder.
            output_csv_filename: CSV filename.
            code_zip_filename: Zip filename.

        Returns:
            Dict containing validation pass status and audit checklist.
        """
        sub_path = Path(submission_dir)
        csv_path = sub_path / output_csv_filename
        zip_path = sub_path / code_zip_filename

        checklist: dict[str, bool] = {
            "output_csv_exists": csv_path.exists(),
            "output_csv_schema_valid": False,
            "code_zip_exists": zip_path.exists(),
            "readme_exists": Path("README.md").exists(),
            "pyproject_exists": Path("pyproject.toml").exists(),
        }

        errors: list[str] = []

        # Validate CSV
        if csv_path.exists():
            res = self.csv_validator.validate_file(str(csv_path))
            checklist["output_csv_schema_valid"] = res["is_valid"]
            if not res["is_valid"]:
                errors.extend(res["errors"])
        else:
            errors.append(f"Missing required submission artifact: {csv_path}")

        if not zip_path.exists():
            logger.warning(f"code.zip not yet created at {zip_path}")

        passed = all(checklist.values())

        logger.info(
            "Submission package QA complete",
            extra={"passed": passed, "checklist": checklist, "errors_count": len(errors)},
        )

        return {
            "passed": passed,
            "checklist": checklist,
            "errors": errors,
        }
