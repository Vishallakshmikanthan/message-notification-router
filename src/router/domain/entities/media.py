"""MediaManifest, ImageManifest, and VoiceNoteManifest Domain Entities."""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass(frozen=True)
class MediaManifest:
    """Base Media manifest entity holding shared media attributes."""

    media_id: str
    media_type: str = "image"
    file_path: str = ""
    file_size_bytes: int = 0


@dataclass(frozen=True)
class ImageManifest:
    """Image media manifest matching images.csv."""

    media_id: str = ""
    image_id: str = ""
    file_path: str = ""
    file_size_bytes: int = 0
    width_px: int = 0
    height_px: int = 0
    mime_type: str = "image/jpeg"
    ocr_text: Optional[str] = None
    vlm_caption: Optional[str] = None
    media_category: Optional[str] = None
    has_qr_code: bool = False

    def __post_init__(self) -> None:
        if not self.media_id and self.image_id:
            object.__setattr__(self, "media_id", self.image_id)
        elif not self.image_id and self.media_id:
            object.__setattr__(self, "image_id", self.media_id)


@dataclass(frozen=True)
class VoiceNoteManifest:
    """Voice note media manifest matching voice_notes.csv."""

    media_id: str = ""
    voice_note_id: str = ""
    file_path: str = ""
    duration_seconds: float = 0.0
    audio_codec: str = "opus"
    file_size_bytes: int = 0
    transcript: Optional[str] = None
    acoustic_tone: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.media_id and self.voice_note_id:
            object.__setattr__(self, "media_id", self.voice_note_id)
        elif not self.voice_note_id and self.media_id:
            object.__setattr__(self, "voice_note_id", self.media_id)
