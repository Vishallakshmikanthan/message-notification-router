"""SchemaValidator implementation for dataset integrity verification."""

from typing import Any, Mapping

from router.core.logging.logger import get_logger
from router.infrastructure.storage.quarantine_engine import QuarantineEngine

logger = get_logger(__name__)


class SchemaValidator:
    """Executes 4-level integrity and constraint verification over CSV datasets."""

    def __init__(self, quarantine_engine: QuarantineEngine | None = None) -> None:
        """Initialize SchemaValidator with optional QuarantineEngine instance."""
        self.quarantine_engine = quarantine_engine or QuarantineEngine()

    def validate_row(
        self, row: Mapping[str, Any], required_fields: list[str], dataset_name: str
    ) -> bool:
        """Validate row field presence and non-null constraints."""
        for field_name in required_fields:
            if field_name not in row or row[field_name] is None:
                self.quarantine_engine.quarantine_row(
                    row=row,
                    reason=f"Missing required field: {field_name}",
                    dataset_name=dataset_name,
                )
                return False
        return True

    def validate_foreign_key(
        self,
        fk_value: Any,
        target_keys: set[Any],
        fk_name: str,
        dataset_name: str,
        row: Mapping[str, Any],
    ) -> bool:
        """Validate foreign key referential integrity against target key set."""
        if fk_value is None:
            return True  # Nullable FK allowed
        if fk_value not in target_keys:
            self.quarantine_engine.quarantine_row(
                row=row,
                reason=f"Foreign key violation for {fk_name}='{fk_value}'",
                dataset_name=dataset_name,
            )
            return False
        return True
