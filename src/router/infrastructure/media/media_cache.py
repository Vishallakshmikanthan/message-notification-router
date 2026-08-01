"""5-Tier Content-Addressed Media Cache implementation (Media Content, OCR, Transcript, VLM, Summary)."""

import logging
import time
from typing import Any

from router.domain.entities.media_context import OCRResult, QRPayload, TableStructure, TextBlock
from router.domain.ports.media_ports import MediaCachePort

logger = logging.getLogger(__name__)


class MediaCache(MediaCachePort):
    """5-Tier Content-Addressed Caching System implementing RAM/KV storage with cryptographic SHA-256 keys."""

    def __init__(self, ttl_seconds: int = 86400):
        self.ttl_seconds = ttl_seconds
        # In-memory storage stores for 5 tiers
        self._content_tier: dict[str, bytes] = {}
        self._ocr_tier: dict[str, dict[str, Any]] = {}
        self._transcript_tier: dict[str, dict[str, Any]] = {}
        self._vlm_tier: dict[str, dict[str, Any]] = {}
        self._summary_tier: dict[str, dict[str, Any]] = {}
        self._timestamps: dict[str, float] = {}

    def get_content(self, sha256_hash: str) -> bytes | None:
        """Tier 1: Media Content Cache lookup (`media:content:{hash}`)."""
        key = f"media:content:{sha256_hash}"
        if self._is_expired(key):
            self.delete_key(key)
            return None

        val = self._content_tier.get(key)
        if val is not None:
            logger.debug(f"Cache HIT [Tier 1 Content]: {key}")
        return val

    def set_content(self, sha256_hash: str, content: bytes) -> None:
        """Tier 1: Store raw/normalized asset bytes."""
        key = f"media:content:{sha256_hash}"
        self._content_tier[key] = content
        self._timestamps[key] = time.time()
        logger.debug(f"Cache STORE [Tier 1 Content]: {key} ({len(content)} bytes)")

    def get_ocr(self, sha256_hash: str) -> OCRResult | None:
        """Tier 2: OCR Cache lookup (`ocr:v2:{hash}`)."""
        key = f"ocr:v2:{sha256_hash}"
        if self._is_expired(key):
            self.delete_key(key)
            return None

        data = self._ocr_tier.get(key)
        if data is None:
            return None

        logger.debug(f"Cache HIT [Tier 2 OCR]: {key}")
        return self._deserialize_ocr_result(data)

    def set_ocr(self, sha256_hash: str, ocr_result: OCRResult) -> None:
        """Tier 2: Store serialized OCR result."""
        key = f"ocr:v2:{sha256_hash}"
        self._ocr_tier[key] = self._serialize_ocr_result(ocr_result)
        self._timestamps[key] = time.time()
        logger.debug(f"Cache STORE [Tier 2 OCR]: {key}")

    def get_transcript(self, sha256_hash: str) -> dict[str, Any] | None:
        """Tier 3: Transcript Cache lookup (`asr:whisper-l3:{hash}`)."""
        key = f"asr:whisper-l3:{sha256_hash}"
        if self._is_expired(key):
            self.delete_key(key)
            return None

        val = self._transcript_tier.get(key)
        if val is not None:
            logger.debug(f"Cache HIT [Tier 3 Transcript]: {key}")
        return val

    def set_transcript(self, sha256_hash: str, transcript_data: dict[str, Any]) -> None:
        """Tier 3: Store transcript payload."""
        key = f"asr:whisper-l3:{sha256_hash}"
        self._transcript_tier[key] = transcript_data
        self._timestamps[key] = time.time()
        logger.debug(f"Cache STORE [Tier 3 Transcript]: {key}")

    def get_vlm(self, sha256_hash: str) -> dict[str, Any] | None:
        """Tier 4: VLM / Caption Cache lookup (`vlm:siglip:{hash}`)."""
        key = f"vlm:siglip:{sha256_hash}"
        if self._is_expired(key):
            self.delete_key(key)
            return None

        val = self._vlm_tier.get(key)
        if val is not None:
            logger.debug(f"Cache HIT [Tier 4 VLM]: {key}")
        return val

    def set_vlm(self, sha256_hash: str, vlm_data: dict[str, Any]) -> None:
        """Tier 4: Store VLM perception payload."""
        key = f"vlm:siglip:{sha256_hash}"
        self._vlm_tier[key] = vlm_data
        self._timestamps[key] = time.time()
        logger.debug(f"Cache STORE [Tier 4 VLM]: {key}")

    def get_summary(self, sha256_hash: str) -> dict[str, Any] | None:
        """Tier 5: Summary Cache lookup (`summary:v1:{hash}`)."""
        key = f"summary:v1:{sha256_hash}"
        if self._is_expired(key):
            self.delete_key(key)
            return None

        val = self._summary_tier.get(key)
        if val is not None:
            logger.debug(f"Cache HIT [Tier 5 Summary]: {key}")
        return val

    def set_summary(self, sha256_hash: str, summary_data: dict[str, Any]) -> None:
        """Tier 5: Store synthesized summary dictionary."""
        key = f"summary:v1:{sha256_hash}"
        self._summary_tier[key] = summary_data
        self._timestamps[key] = time.time()
        logger.debug(f"Cache STORE [Tier 5 Summary]: {key}")

    def delete_key(self, key: str) -> None:
        """Delete key from cache tiers."""
        self._content_tier.pop(key, None)
        self._ocr_tier.pop(key, None)
        self._transcript_tier.pop(key, None)
        self._vlm_tier.pop(key, None)
        self._summary_tier.pop(key, None)
        self._timestamps.pop(key, None)

    def _is_expired(self, key: str) -> bool:
        """Check if cache key timestamp exceeds TTL."""
        t = self._timestamps.get(key)
        if t is None:
            return False
        return (time.time() - t) > self.ttl_seconds

    def _serialize_ocr_result(self, ocr_result: OCRResult) -> dict[str, Any]:
        """Serialize OCRResult dataclass into JSON-serializable dictionary."""
        return {
            "full_extracted_text": ocr_result.full_extracted_text,
            "mean_confidence": ocr_result.mean_confidence,
            "engine_used": ocr_result.engine_used,
            "detected_language_scripts": ocr_result.detected_language_scripts,
            "text_blocks": [
                {
                    "block_id": b.block_id,
                    "text": b.text,
                    "confidence": b.confidence,
                    "bounding_box": b.bounding_box,
                    "reading_order_index": b.reading_order_index,
                    "font_size_category": b.font_size_category,
                }
                for b in ocr_result.text_blocks
            ],
            "detected_tables": [
                {
                    "table_id": t.table_id,
                    "num_rows": t.num_rows,
                    "num_cols": t.num_cols,
                    "headers": t.headers,
                    "rows": t.rows,
                    "markdown_representation": t.markdown_representation,
                    "bounding_box": t.bounding_box,
                }
                for t in ocr_result.detected_tables
            ],
            "qr_codes": [
                {
                    "qr_id": q.qr_id,
                    "raw_content": q.raw_content,
                    "payload_type": q.payload_type,
                    "parsed_metadata": q.parsed_metadata,
                    "bounding_box": q.bounding_box,
                }
                for q in ocr_result.qr_codes
            ],
        }

    def _deserialize_ocr_result(self, data: dict[str, Any]) -> OCRResult:
        """Deserialize dictionary back into OCRResult dataclass."""
        blocks = [
            TextBlock(
                block_id=b["block_id"],
                text=b["text"],
                confidence=b["confidence"],
                bounding_box=b["bounding_box"],
                reading_order_index=b.get("reading_order_index", 0),
                font_size_category=b.get("font_size_category", "BODY"),
            )
            for b in data.get("text_blocks", [])
        ]
        tables = [
            TableStructure(
                table_id=t["table_id"],
                num_rows=t["num_rows"],
                num_cols=t["num_cols"],
                headers=t["headers"],
                rows=t["rows"],
                markdown_representation=t["markdown_representation"],
                bounding_box=t.get("bounding_box", [0.0, 0.0, 1.0, 1.0]),
            )
            for t in data.get("detected_tables", [])
        ]
        qrs = [
            QRPayload(
                qr_id=q["qr_id"],
                raw_content=q["raw_content"],
                payload_type=q["payload_type"],
                parsed_metadata=q.get("parsed_metadata", {}),
                bounding_box=q.get("bounding_box", [0.0, 0.0, 1.0, 1.0]),
            )
            for q in data.get("qr_codes", [])
        ]

        return OCRResult(
            full_extracted_text=data.get("full_extracted_text", ""),
            mean_confidence=data.get("mean_confidence", 1.0),
            text_blocks=blocks,
            detected_tables=tables,
            qr_codes=qrs,
            detected_language_scripts=data.get("detected_language_scripts", ["Latin"]),
            engine_used=data.get("engine_used", "PADDLEOCR"),
        )
