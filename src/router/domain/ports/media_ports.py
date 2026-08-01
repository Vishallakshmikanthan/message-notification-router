"""Domain Port Interfaces for Multimodal Media Processing (Validation, OCR, ASR, Processing, Caching)."""

from abc import ABC, abstractmethod
from typing import Any

from router.domain.entities.media_context import ImageContext, OCRResult, VoiceContext


class MediaValidatorPort(ABC):
    """Port interface for multi-stage visual and acoustic file integrity & boundary validation."""

    @abstractmethod
    def validate_image(self, file_path: str) -> tuple[bool, dict[str, Any]]:
        """Validate image existence, magic bytes, dimensions, and mime-type.

        Returns (is_valid, metadata_dict).
        """
        pass

    @abstractmethod
    def validate_voice(self, file_path: str) -> tuple[bool, dict[str, Any]]:
        """Validate audio header, duration bounds, and non-zero frames.

        Returns (is_valid, metadata_dict).
        """
        pass


class OCRProcessorPort(ABC):
    """Port interface for Optical Character Recognition, layout, table & QR extraction."""

    @abstractmethod
    def extract_text(self, file_path: str) -> OCRResult:
        """Extract text blocks, bounding boxes, tables, and QR codes from image file."""
        pass


class WhisperIntegrationPort(ABC):
    """Port interface for Automated Speech Recognition via Faster-Whisper."""

    @abstractmethod
    def transcribe_audio(self, file_path: str) -> dict[str, Any]:
        """Transcribe 16kHz audio buffer into transcript, word timestamps, and language code."""
        pass


class ImageProcessorPort(ABC):
    """Port interface for full image preprocessing, visual perception, 14-category classification & ImageContext synthesis."""

    @abstractmethod
    def process_image(self, image_id: str, file_path: str, sha256_hash: str) -> ImageContext:
        """Process image file into populated ImageContext."""
        pass


class VoiceProcessorPort(ABC):
    """Port interface for audio transcoding, VAD, acoustic profiling, dual-modal urgency & VoiceContext synthesis."""

    @abstractmethod
    def process_voice(self, voice_note_id: str, file_path: str, sha256_hash: str) -> VoiceContext:
        """Process voice note file into populated VoiceContext."""
        pass


class MediaCachePort(ABC):
    """Port interface for 5-tier content-addressed media caching system."""

    @abstractmethod
    def get_content(self, sha256_hash: str) -> bytes | None:
        """Tier 1: Media Content Cache."""
        pass

    @abstractmethod
    def set_content(self, sha256_hash: str, content: bytes) -> None:
        """Tier 1: Store raw/normalized asset bytes."""
        pass

    @abstractmethod
    def get_ocr(self, sha256_hash: str) -> OCRResult | None:
        """Tier 2: OCR Cache lookup."""
        pass

    @abstractmethod
    def set_ocr(self, sha256_hash: str, ocr_result: OCRResult) -> None:
        """Tier 2: Store OCR result."""
        pass

    @abstractmethod
    def get_transcript(self, sha256_hash: str) -> dict[str, Any] | None:
        """Tier 3: Transcript Cache lookup."""
        pass

    @abstractmethod
    def set_transcript(self, sha256_hash: str, transcript_data: dict[str, Any]) -> None:
        """Tier 3: Store transcript payload."""
        pass

    @abstractmethod
    def get_vlm(self, sha256_hash: str) -> dict[str, Any] | None:
        """Tier 4: VLM / Caption Cache lookup."""
        pass

    @abstractmethod
    def set_vlm(self, sha256_hash: str, vlm_data: dict[str, Any]) -> None:
        """Tier 4: Store VLM perception payload."""
        pass

    @abstractmethod
    def get_summary(self, sha256_hash: str) -> dict[str, Any] | None:
        """Tier 5: Summary Cache lookup."""
        pass

    @abstractmethod
    def set_summary(self, sha256_hash: str, summary_data: dict[str, Any]) -> None:
        """Tier 5: Store synthesized summary dictionary."""
        pass
