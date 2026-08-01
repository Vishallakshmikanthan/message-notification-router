"""Unit tests for ImageProcessor handling 14-category classification, visual perception, indicator score synthesis, and ImageContext generation."""

import os
import tempfile

from router.infrastructure.media.image_processor import ImageProcessor
from router.infrastructure.media.media_validator import MediaValidator
from router.infrastructure.media.ocr_processor import OCRProcessor


def test_image_processor_payment_screenshot() -> None:
    validator = MediaValidator()
    ocr = OCRProcessor()
    processor = ImageProcessor(validator=validator, ocr_processor=ocr)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(b"\xff\xd8\xff\xe0" + b"\x00" * 1000)
        tmp_path = tmp.name

    sidecar = tmp_path + ".txt"
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write("PAYMENT SUCCESSFUL\nTRANSFER TO JOHN DOE\nTRANSACTION ID: TXN100293\nAMOUNT: ₹500.00\n")

    try:
        img_ctx = processor.process_image(
            image_id="img_101",
            file_path=tmp_path,
            sha256_hash="dummy_hash_123",
        )

        assert img_ctx.image_id == "img_101"
        assert img_ctx.primary_category == "PAYMENT_SCREENSHOTS"
        assert img_ctx.category_confidence >= 0.90
        assert "PAYMENT SUCCESSFUL" in img_ctx.extracted_text
        assert img_ctx.business_indicators["score"] > 0.5
        assert len(img_ctx.overall_summary) > 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(sidecar):
            os.remove(sidecar)


def test_image_processor_scam_detection() -> None:
    validator = MediaValidator()
    ocr = OCRProcessor()
    processor = ImageProcessor(validator=validator, ocr_processor=ocr)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 1000)
        tmp_path = tmp.name

    sidecar = tmp_path + ".txt"
    with open(sidecar, "w", encoding="utf-8") as f:
        f.write("YOU WON A LOTTERY OF $10,000! CLAIM IMMEDIATELY!\n")

    try:
        img_ctx = processor.process_image(
            image_id="img_scam_1",
            file_path=tmp_path,
            sha256_hash="scam_hash_456",
        )

        assert img_ctx.primary_category == "SCAM_IMAGES"
        assert img_ctx.scam_indicators["score"] > 0.9
        assert img_ctx.urgency_indicators["score"] > 0.5
        assert "scam" in img_ctx.overall_summary.lower()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(sidecar):
            os.remove(sidecar)
