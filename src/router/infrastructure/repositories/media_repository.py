"""MediaRepository implementation matching images.csv and voice_notes.csv."""

from router.domain.entities.media import ImageManifest, VoiceNoteManifest
from router.domain.ports.repository_ports import IMediaRepository
from router.infrastructure.repositories.base_repository import BaseRepository


class MediaRepository(
    BaseRepository[ImageManifest | VoiceNoteManifest, str], IMediaRepository
):
    """Manages media manifests for images and voice notes."""

    def __init__(self) -> None:
        """Initialize MediaRepository typed indexes."""
        super().__init__()
        self._image_index: dict[str, ImageManifest] = {}
        self._voice_index: dict[str, VoiceNoteManifest] = {}

    def add_image(self, image: ImageManifest) -> None:
        """Add image manifest entity."""
        super().add(image.media_id, image)
        self._image_index[image.media_id] = image

    def add_voice(self, voice: VoiceNoteManifest) -> None:
        """Add voice note manifest entity."""
        super().add(voice.media_id, voice)
        self._voice_index[voice.media_id] = voice

    def get_image(self, media_id: str) -> ImageManifest | None:
        """Get image manifest entity by ID."""
        return self._image_index.get(media_id)

    def get_voice(self, media_id: str) -> VoiceNoteManifest | None:
        """Get voice note manifest entity by ID."""
        return self._voice_index.get(media_id)

    def clear(self) -> None:
        """Clear store and typed indexes."""
        super().clear()
        self._image_index.clear()
        self._voice_index.clear()
