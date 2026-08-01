"""Unit tests for MediaPipelineService orchestrating end-to-end media processing, cache hits, and MediaContext synthesis."""

import os
import tempfile

from router.application.media.media_pipeline_service import MediaPipelineService
from router.infrastructure.media.image_processor import ImageProcessor
from router.infrastructure.media.media_cache import MediaCache
from router.infrastructure.media.media_validator import MediaValidator
from router.infrastructure.media.ocr_processor import OCRProcessor
from router.infrastructure.media.voice_processor import VoiceProcessor
from router.infrastructure.media.whisper_integration import WhisperIntegration


def test_media_pipeline_service_image_flow() -> None:
    validator = MediaValidator()
    ocr = OCRProcessor()
    img_proc = ImageProcessor(validator=validator, ocr_processor=ocr)
    whisper = WhisperIntegration()
    voice_proc = VoiceProcessor(validator=validator, whisper_integration=whisper)
    cache = MediaCache()

    service = MediaPipelineService(
        validator=validator,
        image_processor=img_proc,
        voice_processor=voice_proc,
        cache=cache,
    )

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(b"\xff\xd8\xff\xe0" + b"\x00" * 1000)
        tmp_path = tmp.name

    sidecar = tmp_path + ".txt"
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write("OFFICIAL GOVERNMENT NOTICE\nMEMORANDUM REGARDING SAFETY\n")

    try:
        # First call (Cache Miss)
        media_ctx = service.process_media(
            media_id="media_img_1",
            media_type="IMAGE",
            file_path=tmp_path,
        )

        assert media_ctx.media_id == "media_img_1"
        assert media_ctx.media_type == "IMAGE"
        assert media_ctx.validation_status == "VALIDATED"
        assert media_ctx.image_context is not None
        assert media_ctx.image_category == "GOVERNMENT_NOTICES"
        assert media_ctx.processing_latency_ms > 0

        # Second call (Cache Hit)
        cached_media_ctx = service.process_media(
            media_id="media_img_1",
            media_type="IMAGE",
            file_path=tmp_path,
        )

        assert cached_media_ctx.media_id == "media_img_1"
        assert cached_media_ctx.image_category == "GOVERNMENT_NOTICES"
        assert cached_media_ctx.processing_latency_ms >= 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(sidecar):
            os.remove(sidecar)


def test_media_pipeline_service_voice_flow() -> None:
    validator = MediaValidator()
    ocr = OCRProcessor()
    img_proc = ImageProcessor(validator=validator, ocr_processor=ocr)
    whisper = WhisperIntegration()
    voice_proc = VoiceProcessor(validator=validator, whisper_integration=whisper)
    cache = MediaCache()

    service = MediaPipelineService(
        validator=validator,
        image_processor=img_proc,
        voice_processor=voice_proc,
        cache=cache,
    )

    with tempfile.NamedTemporaryFile(suffix=".opus", delete=False) as tmp:
        tmp.write(b"OggS" + b"\x00" * 30000)
        tmp_path = tmp.name

    try:
        media_ctx = service.process_media(
            media_id="media_voice_1",
            media_type="VOICE",
            file_path=tmp_path,
        )

        assert media_ctx.media_id == "media_voice_1"
        assert media_ctx.media_type == "VOICE"
        assert media_ctx.validation_status == "VALIDATED"
        assert media_ctx.voice_context is not None
        assert len(media_ctx.voice_transcript) > 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
