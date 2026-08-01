"""Domain models for Multimodal Media processing (ImageContext, VoiceContext, OCR data structures)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TextBlock:
    """Represents an individual text block or paragraph in an image asset."""

    block_id: int
    text: str
    confidence: float
    bounding_box: list[float]  # [xmin, ymin, xmax, ymax] normalized to [0.0, 1.0]
    reading_order_index: int = 0
    font_size_category: str = "BODY"  # HEADER, SUBHEADER, BODY, CAPTION, FOOTNOTE


@dataclass(frozen=True)
class TableStructure:
    """Represents a structured table extracted from an image asset."""

    table_id: int
    num_rows: int
    num_cols: int
    headers: list[str]
    rows: list[list[str]]
    markdown_representation: str
    bounding_box: list[float] = field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])


@dataclass(frozen=True)
class QRPayload:
    """Represents a decoded 2D QR code or barcode matrix payload."""

    qr_id: int
    raw_content: str
    payload_type: str  # UPI_PAYMENT, URL, WIFI, VCARD, PLAIN_TEXT
    parsed_metadata: dict[str, str] = field(default_factory=dict)
    bounding_box: list[float] = field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])


@dataclass(frozen=True)
class OCRResult:
    """Container for all OCR extractions from an image asset."""

    full_extracted_text: str
    mean_confidence: float
    text_blocks: list[TextBlock] = field(default_factory=list)
    detected_tables: list[TableStructure] = field(default_factory=list)
    qr_codes: list[QRPayload] = field(default_factory=list)
    detected_language_scripts: list[str] = field(default_factory=lambda: ["Latin"])
    engine_used: str = "PADDLEOCR"


@dataclass(frozen=True)
class ImageContext:
    """Immutable domain context for processed visual media."""

    image_id: str
    sha256_hash: str
    dimensions: tuple[int, int]
    aspect_ratio: float
    primary_category: str  # One of 14 categories defined in image_pipeline.md
    secondary_categories: list[str] = field(default_factory=list)
    category_confidence: float = 1.0
    extracted_text: str = ""
    ocr_confidence: float = 1.0
    text_blocks: list[TextBlock] = field(default_factory=list)
    detected_tables: list[TableStructure] = field(default_factory=list)
    qr_payloads: list[QRPayload] = field(default_factory=list)
    visual_objects: list[str] = field(default_factory=list)
    scene_description: str = ""
    image_purpose: str = ""
    risk_indicators: dict[str, Any] = field(default_factory=lambda: {"score": 0.0, "flags": []})
    business_indicators: dict[str, Any] = field(default_factory=lambda: {"score": 0.0, "brand_name": ""})
    urgency_indicators: dict[str, Any] = field(default_factory=lambda: {"score": 0.0, "keywords": []})
    event_indicators: dict[str, Any] = field(default_factory=lambda: {"score": 0.0, "event_date": ""})
    spam_indicators: dict[str, Any] = field(default_factory=lambda: {"score": 0.0, "reason": ""})
    scam_indicators: dict[str, Any] = field(default_factory=lambda: {"score": 0.0, "tactic": ""})
    overall_summary: str = ""


@dataclass(frozen=True)
class WordTimestamp:
    """Millisecond boundary offset alignment for transcribed speech words."""

    word: str
    start_ms: int
    end_ms: int
    confidence: float = 1.0


@dataclass(frozen=True)
class VoiceContext:
    """Immutable domain context for processed acoustic voice media."""

    voice_note_id: str
    sha256_hash: str
    duration_seconds: float
    sample_rate_hz: int = 16000
    audio_channels: int = 1
    transcript: str = ""
    transcript_confidence: float = 1.0
    word_timestamps: list[WordTimestamp] = field(default_factory=list)
    detected_language: str = "en"
    language_confidence: float = 1.0
    speaker_profile: dict[str, Any] = field(
        default_factory=lambda: {
            "mean_pitch_hz": 180.0,
            "wpm": 140.0,
            "silence_ratio": 0.1,
            "mean_energy_db": -24.0,
        }
    )
    acoustic_tone: str = "NEUTRAL"  # CALM, URGENT, SHOUTING, HESITANT, NEUTRAL
    urgency_score: float = 0.0
    key_entities: list[dict[str, str]] = field(default_factory=list)
    key_topics: list[str] = field(default_factory=list)
    overall_summary: str = ""
