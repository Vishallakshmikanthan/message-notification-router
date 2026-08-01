"""Unit tests for OCRProcessor handling OCR extraction, table markdown conversion, and QR payload decoding."""

import os
import tempfile

from router.infrastructure.media.ocr_processor import OCRProcessor


def test_ocr_processor_text_extraction() -> None:
    processor = OCRProcessor()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(b"dummy image bytes")
        tmp_path = tmp.name

    # Write text sidecar hint
    sidecar_path = tmp_path + ".txt"
    with open(sidecar_path, "w", encoding="utf-8") as f:
        f.write("INVOICE #90812\nTOTAL AMOUNT: S250.00\nupi://pay?pa=merchant@upi&am=250.00\n")

    try:
        ocr_result = processor.extract_text(tmp_path)
        assert ocr_result.mean_confidence > 0.0
        assert "INVOICE #90812" in ocr_result.full_extracted_text
        assert "$250.00" in ocr_result.full_extracted_text  # S250.00 -> $250.00 regex cleaning
        assert len(ocr_result.qr_codes) == 1
        assert ocr_result.qr_codes[0].payload_type == "UPI_PAYMENT"
        assert ocr_result.qr_codes[0].parsed_metadata.get("pa") == "merchant@upi"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(sidecar_path):
            os.remove(sidecar_path)


def test_ocr_processor_table_reconstruction() -> None:
    processor = OCRProcessor()
    text = "Item | Qty | Price\nLaptop | 1 | $1200\nMouse | 2 | $50"

    tables = processor._extract_tables("dummy.png", text)
    assert len(tables) == 1
    assert tables[0].num_rows == 3
    assert tables[0].num_cols == 3
    assert "| Item | Qty | Price |" in tables[0].markdown_representation
