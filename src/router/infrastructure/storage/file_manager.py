"""FileManager implementation for disk file system auditing and path resolution."""

import os
from typing import Set

from router.core.logging.logger import get_logger

logger = get_logger(__name__)


class FileManager:
    """Audits disk media assets and resolves physical path references."""

    def __init__(self, media_dir: str = "./dataset/media") -> None:
        """Initialize FileManager with media directory path."""
        self.media_dir = media_dir
        self._valid_paths: Set[str] = set()

    def audit_media_directories(self) -> Set[str]:
        """Audit physical media directories and cache valid file paths."""
        logger.info("Auditing media directory", path=self.media_dir)
        valid_paths: Set[str] = set()
        if os.path.exists(self.media_dir) and os.path.isdir(self.media_dir):
            for root, _, files in os.walk(self.media_dir):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), self.media_dir)
                    valid_paths.add(rel_path.replace("\\", "/"))
        self._valid_paths = valid_paths
        logger.info("Media audit complete", total_files=len(self._valid_paths))
        return self._valid_paths

    def verify_file_exists(self, file_path: str) -> bool:
        """Verify physical existence of a media file path."""
        normalized = file_path.replace("\\", "/")
        if normalized in self._valid_paths:
            return True
        return os.path.exists(file_path)
