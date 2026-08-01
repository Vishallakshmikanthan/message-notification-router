"""Unit tests for MediaValidator inspecting magic bytes, header limits, dimensions, and audio duration."""

import os
import tempfile

from router.infrastructure.media.media_validator import MediaValidator


def test_validate_image_valid_jpeg() -> None:
    validator = MediaValidator()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        # Write JPEG magic bytes \xFF\xD8\xFF\xE0
        tmp.write(b"\xff\xd8\xff\xe0" + b"\x00" * 500)
        tmp_path = tmp.name

    try:
        is_valid, meta = validator.validate_image(tmp_path)
        assert is_valid is True
        assert meta["mime_type"] == "image/jpeg"
        assert meta["status"] == "VALIDATED"
        assert meta["width"] >= 64
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_validate_image_non_existent() -> None:
    validator = MediaValidator()
    is_valid, meta = validator.validate_image("non_existent_file.png")
    assert is_valid is False
    assert meta["error"] == "FILE_NOT_FOUND"


def test_validate_voice_valid_ogg() -> None:
    validator = MediaValidator()
    with tempfile.NamedTemporaryFile(suffix=".opus", delete=False) as tmp:
        # Write Ogg magic bytes OggS
        tmp.write(b"OggS" + b"\x00" * 40000)  # ~10 sec simulation
        tmp_path = tmp.name

    try:
        is_valid, meta = validator.validate_voice(tmp_path)
        assert is_valid is True
        assert meta["audio_format"] == "ogg/opus"
        assert meta["duration_seconds"] >= 0.5
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_validate_voice_empty_file() -> None:
    validator = MediaValidator()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        is_valid, meta = validator.validate_voice(tmp_path)
        assert is_valid is False
        assert meta["error"] == "EMPTY_FILE"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
