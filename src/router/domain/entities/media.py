"""MediaManifest, ImageManifest, and VoiceNoteManifest Domain Entities."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MediaManifest:
    """Base Media manifest entity holding shared media attributes."""

    media_id: str
    media_type: Literal["image", "voice"]
    file_path: str
    file_size_bytes: int = 0


@dataclass(frozen=True)
class ImageManifest(MediaManifest):
    """Image media manifest matching images.csv."""

    ocr_text: str | None = None
    vlm_caption: str | None = None
    media_category: str | None = None
    has_qr_code: bool = False


@dataclass(frozen=True)
class VoiceNoteManifest(MediaManifest):
    """Voice note media manifest matching voice_notes.csv."""

    duration_seconds: float = 0.0
    transcript: str | None = None
    acoustic_tone: str | None = None
