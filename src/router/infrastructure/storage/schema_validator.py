"""SchemaValidator implementing 4-Level Validation Hierarchy specified in validation_strategy.md."""

import re
from collections.abc import Mapping
from typing import Any

from router.core.logging.logger import get_logger
from router.infrastructure.storage.quarantine_engine import QuarantineEngine

logger = get_logger(__name__)


class SchemaValidator:
    """Executes 4-level integrity and constraint verification over CSV datasets."""

    # Level 2 Regex Patterns
    PK_PATTERNS = {
        "user_id": re.compile(r"^u_\d{3}$"),
        "group_id": re.compile(r"^group_\d{3}$"),
        "business_id": re.compile(r"^business_\d{3}$"),
        "message_id": re.compile(r"^msg_\d{3}$"),
        "image_id": re.compile(r"^img_\d{3}$"),
        "voice_note_id": re.compile(r"^voice_\d{3}$"),
    }

    def __init__(self, quarantine_engine: QuarantineEngine | None = None) -> None:
        """Initialize SchemaValidator with QuarantineEngine instance."""
        self.quarantine_engine = quarantine_engine or QuarantineEngine()

    def validate_level1_structure(
        self, row: Mapping[str, Any], expected_columns: list[str], dataset_name: str
    ) -> bool:
        """Level 1: File & Structural Validation (column matching)."""
        for col in expected_columns:
            if col not in row:
                self.quarantine_engine.quarantine_row(
                    row=row,
                    reason=f"Level 1 structural error: Missing expected column '{col}'",
                    dataset_name=dataset_name,
                )
                return False
        return True

    def validate_level2_types_and_formats(
        self,
        row: Mapping[str, Any],
        pk_field: str | None,
        pk_type: str | None,
        dataset_name: str,
    ) -> bool:
        """Level 2: Field Type & Regex Format Validation."""
        # 1. Primary Key Format check
        if pk_field and pk_type in self.PK_PATTERNS:
            val = row.get(pk_field)
            if not val or not isinstance(val, str) or not self.PK_PATTERNS[pk_type].match(val.strip()):
                self.quarantine_engine.quarantine_row(
                    row=row,
                    reason=f"Level 2 format error: Invalid {pk_type} format for '{pk_field}' = '{val}'",
                    dataset_name=dataset_name,
                )
                return False

        # 2. Non-negative counters check
        for field, val in row.items():
            if field.endswith(("_count", "_30d", "_180d", "_volume", "_received", "_opened", "_dismissed")):
                if val is not None and val != "":
                    try:
                        num_val = float(val)
                        if num_val < 0:
                            self.quarantine_engine.quarantine_row(
                                row=row,
                                reason=f"Level 2 constraint error: Field '{field}' value {num_val} is negative",
                                dataset_name=dataset_name,
                            )
                            return False
                    except (ValueError, TypeError):
                        pass

        return True

    def validate_foreign_key(
        self,
        fk_value: Any,
        target_keys: set[Any],
        fk_name: str,
        dataset_name: str,
        row: Mapping[str, Any],
    ) -> bool:
        """Level 3: Foreign Key & Referential Integrity Verification."""
        if fk_value is None or str(fk_value).strip() == "" or str(fk_value).upper() == "NONE":
            return True  # Nullable FK allowed

        val_str = str(fk_value).strip()
        if val_str not in target_keys:
            self.quarantine_engine.quarantine_row(
                row=row,
                reason=f"Level 3 FK failure: '{fk_name}'='{val_str}' not found in target primary key set",
                dataset_name=dataset_name,
            )
            return False
        return True

    def validate_level4_domain_rules(self, row: Mapping[str, Any], dataset_name: str) -> bool:
        """Level 4: Domain & Business Rules Constraints Verification."""
        if dataset_name == "groups.csv":
            try:
                member_count = int(row.get("member_count", 0))
                admin_count = int(row.get("admin_count", 0))
                if member_count < admin_count:
                    self.quarantine_engine.quarantine_row(
                        row=row,
                        reason=f"Level 4 domain invariant failure: member_count ({member_count}) < admin_count ({admin_count})",
                        dataset_name=dataset_name,
                    )
                    return False
            except (ValueError, TypeError):
                pass

        elif dataset_name == "messages.csv":
            conv_type = str(row.get("conversation_type", "")).lower()
            group_id = row.get("group_id")
            business_id = row.get("business_id")
            media_type = row.get("media_type")
            media_id = row.get("media_id")

            if conv_type == "group" and (not group_id or str(group_id).upper() == "NONE"):
                self.quarantine_engine.quarantine_row(
                    row=row,
                    reason="Level 4 domain rule: conversation_type is 'group' but group_id is empty",
                    dataset_name=dataset_name,
                )
                return False

            if conv_type == "business" and (not business_id or str(business_id).upper() == "NONE"):
                self.quarantine_engine.quarantine_row(
                    row=row,
                    reason="Level 4 domain rule: conversation_type is 'business' but business_id is empty",
                    dataset_name=dataset_name,
                )
                return False

            if media_type and str(media_type).lower() in ("image", "voice"):
                if not media_id or str(media_id).upper() == "NONE":
                    self.quarantine_engine.quarantine_row(
                        row=row,
                        reason=f"Level 4 media rule: media_type is '{media_type}' but media_id is missing",
                        dataset_name=dataset_name,
                    )
                    return False

        return True
