"""Output CSV Validation Suite for Hackathon Benchmark Submission.

Implements Submission Artifact Specifications from submission_strategy.md §4.1:
- Header Structure: message_id,action,reason,confidence,evidence
- Action Schema Enforcer: Restricted strictly to 4 allowed actions
- Confidence Schema Enforcer: Bounded strictly between 0.00 and 1.00
- Null Value Guard: Zero empty cells permitted across all rows

Spec: submission_strategy.md §4.1.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"NOTIFY_IMMEDIATELY", "DELIVER_SILENTLY", "SUMMARIZE_IN_BATCH", "DO_NOT_DISTURB"}
REQUIRED_COLUMNS = ["message_id", "action", "reason", "confidence", "evidence"]


class OutputCSVValidator:
    """Validator for output.csv submission files."""

    def __init__(self) -> None:
        """Initialize OutputCSVValidator."""
        pass

    def validate_file(self, csv_path: str) -> Dict[str, Any]:
        """Validate an output.csv file against submission constraints.

        Args:
            csv_path: Path to output.csv file.

        Returns:
            Dict containing validation pass status and detailed error list.
        """
        p = Path(csv_path)
        if not p.exists():
            return {"is_valid": False, "errors": [f"File {csv_path} does not exist"]}

        errors: List[str] = []
        row_count = 0

        with p.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                return {"is_valid": False, "errors": ["File is empty"]}

            # 1. Header Validation
            if headers != REQUIRED_COLUMNS:
                errors.append(f"Header mismatch. Expected {REQUIRED_COLUMNS}, got {headers}")

            # 2. Row Validation
            for idx, row in enumerate(reader, start=2):
                row_count += 1
                if len(row) != len(REQUIRED_COLUMNS):
                    errors.append(f"Row {idx}: Invalid column count ({len(row)} != {len(REQUIRED_COLUMNS)})")
                    continue

                msg_id, action, reason, conf_str, evidence_str = row

                # Null value guard
                if not msg_id.strip():
                    errors.append(f"Row {idx}: Empty message_id")
                if not action.strip():
                    errors.append(f"Row {idx}: Empty action")
                if not reason.strip():
                    errors.append(f"Row {idx}: Empty reason")

                # Action enum guard
                if action.strip() not in VALID_ACTIONS:
                    errors.append(f"Row {idx}: Invalid action '{action}'. Must be one of {VALID_ACTIONS}")

                # Confidence bound guard
                try:
                    conf = float(conf_str)
                    if not (0.0 <= conf <= 1.0):
                        errors.append(f"Row {idx}: Confidence out of bounds ({conf} not in [0.0, 1.0])")
                except ValueError:
                    errors.append(f"Row {idx}: Non-numeric confidence value '{conf_str}'")

        is_valid = len(errors) == 0
        logger.info(
            "output.csv validation complete",
            extra={"path": csv_path, "row_count": row_count, "is_valid": is_valid, "errors_count": len(errors)},
        )

        return {
            "is_valid": is_valid,
            "row_count": row_count,
            "errors": errors,
        }
