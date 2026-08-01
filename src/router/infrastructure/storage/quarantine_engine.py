"""QuarantineEngine implementation for isolating corrupt/invalid CSV rows."""

from typing import Any, Mapping

from router.core.logging.logger import get_logger

logger = get_logger(__name__)


class QuarantineEngine:
    """Isolates malformed dataset rows and logs schema violations."""

    def __init__(self) -> None:
        """Initialize QuarantineEngine isolate storage."""
        self._quarantined_records: list[dict[str, Any]] = []

    def quarantine_row(self, row: Mapping[str, Any], reason: str, dataset_name: str) -> None:
        """Isolate a malformed row and record audit entry."""
        record = {
            "dataset": dataset_name,
            "reason": reason,
            "raw_row": dict(row),
        }
        self._quarantined_records.append(record)
        logger.warning("Record quarantined", dataset=dataset_name, reason=reason)

    def get_quarantined(self) -> list[dict[str, Any]]:
        """Return read-only list of quarantined records."""
        return list(self._quarantined_records)

    def flush_log(self) -> int:
        """Flush quarantine memory log and return cleared count."""
        count = len(self._quarantined_records)
        self._quarantined_records.clear()
        return count
