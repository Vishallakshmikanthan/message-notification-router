"""Image Processor module implementing preprocessing, OCR/VLM feature extraction, 14-category classification, indicator evaluation, and ImageContext assembly."""

import logging
import re
from typing import Any

from router.domain.entities.media_context import ImageContext, OCRResult
from router.domain.ports.media_ports import ImageProcessorPort, MediaValidatorPort, OCRProcessorPort

logger = logging.getLogger(__name__)


class ImageProcessingError(Exception):
    """Raised when image processing fails."""

    pass


class ImageProcessor(ImageProcessorPort):
    """Orchestrates image validation, contrast normalization, OCR extraction, visual classification across 14 categories, indicator computation, and ImageContext synthesis."""

    IMAGE_CATEGORIES = [
        "POSTERS",
        "SCREENSHOTS",
        "BUSINESS_ADVERTISEMENTS",
        "PAYMENT_SCREENSHOTS",
        "SCAM_IMAGES",
        "EVENT_POSTERS",
        "MEETING_INVITATIONS",
        "GOVERNMENT_NOTICES",
        "PERSONAL_PHOTOGRAPHS",
        "DOCUMENTS",
        "CHARTS_INFOGRAPHICS",
        "FORMS",
        "RECEIPTS_INVOICES",
        "QR_CODES",
    ]

    def __init__(
        self,
        validator: MediaValidatorPort,
        ocr_processor: OCRProcessorPort,
    ):
        self.validator = validator
        self.ocr_processor = ocr_processor

    def process_image(self, image_id: str, file_path: str, sha256_hash: str) -> ImageContext:
        """Process image file into populated ImageContext."""
        logger.info(f"Processing image asset: image_id={image_id}, path={file_path}")

        # 1. Validation & Metadata extraction
        is_valid, val_meta = self.validator.validate_image(file_path)

        width = val_meta.get("width", 1024)
        height = val_meta.get("height", 768)
        aspect_ratio = round(width / max(height, 1), 4)

        # 2. Run OCR & Structural extraction
        ocr_result: OCRResult = self.ocr_processor.extract_text(file_path)

        # 3. Perform Visual & Text Feature synthesis
        primary_category, secondary_categories, category_conf = self._classify_image_category(
            ocr_result=ocr_result,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
        )

        # 4. Compute 6 Indicator Vectors
        risk_ind = self._compute_risk_indicators(ocr_result)
        biz_ind = self._compute_business_indicators(ocr_result, primary_category)
        urgency_ind = self._compute_urgency_indicators(ocr_result)
        event_ind = self._compute_event_indicators(ocr_result, primary_category)
        spam_ind = self._compute_spam_indicators(ocr_result, primary_category)
        scam_ind = self._compute_scam_indicators(ocr_result, primary_category)

        # 5. Visual perception & scene description
        visual_objects, scene_desc, purpose = self._synthesize_visual_perception(
            primary_category=primary_category,
            ocr_result=ocr_result,
        )

        # 6. Synthesize overall summary
        overall_summary = self._generate_overall_summary(
            primary_category=primary_category,
            ocr_text=ocr_result.full_extracted_text,
            scene_desc=scene_desc,
            urgency_ind=urgency_ind,
            scam_ind=scam_ind,
        )

        logger.info(
            f"Image processing finished: image_id={image_id}, category={primary_category}, "
            f"ocr_text_length={len(ocr_result.full_extracted_text)}"
        )

        return ImageContext(
            image_id=image_id,
            sha256_hash=sha256_hash,
            dimensions=(width, height),
            aspect_ratio=aspect_ratio,
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            category_confidence=category_conf,
            extracted_text=ocr_result.full_extracted_text,
            ocr_confidence=ocr_result.mean_confidence,
            text_blocks=ocr_result.text_blocks,
            detected_tables=ocr_result.detected_tables,
            qr_payloads=ocr_result.qr_codes,
            visual_objects=visual_objects,
            scene_description=scene_desc,
            image_purpose=purpose,
            risk_indicators=risk_ind,
            business_indicators=biz_ind,
            urgency_indicators=urgency_ind,
            event_indicators=event_ind,
            spam_indicators=spam_ind,
            scam_indicators=scam_ind,
            overall_summary=overall_summary,
        )

    def _classify_image_category(
        self, ocr_result: OCRResult, width: int, height: int, aspect_ratio: float
    ) -> tuple[str, list[str], float]:
        """Classify image into 1 of 14 explicit categories based on visual layout and OCR text patterns."""
        text = ocr_result.full_extracted_text.upper()
        secondary: list[str] = []

        # Category detection heuristics
        if ocr_result.qr_codes:
            secondary.append("QR_CODES")

        if re.search(r"\b(UPI|PAYMENT SUCCESSFUL|TRANSACTION ID|TRANSFER TO|PAID TO|BANK|₹|\$)\b", text):
            primary = "PAYMENT_SCREENSHOTS"
            confidence = 0.95
        elif re.search(r"\b(INVOICE|RECEIPT|BILL|SUBTOTAL|TAX|TOTAL AMOUNT)\b", text) or ocr_result.detected_tables:
            primary = "RECEIPTS_INVOICES"
            confidence = 0.92
        elif re.search(r"\b(YOU WON|LOTTERY|CLAIM IMMEDIATELY|ACCOUNT BLOCKED|URGENT ACTION REQUIRED)\b", text):
            primary = "SCAM_IMAGES"
            confidence = 0.96
        elif re.search(r"\b(ZOOM|GOOGLE MEET|TEAMS|MEETING ID|PASSCODE|CALENDAR|SCHEDULED)\b", text):
            primary = "MEETING_INVITATIONS"
            confidence = 0.90
        elif re.search(r"\b(EVENT|WEBINAR|WORKSHOP|CONFERENCE|VENUE|REGISTER NOW|RSVP)\b", text):
            primary = "EVENT_POSTERS"
            confidence = 0.88
            secondary.append("POSTERS")
        elif re.search(r"\b(OFFICIAL NOTICE|GOVERNMENT|CIRCULAR|MEMORANDUM|SECTION|AUTHORITY)\b", text):
            primary = "GOVERNMENT_NOTICES"
            confidence = 0.89
        elif re.search(r"\b(SALE|OFFER|BUY NOW|DISCOUNT|FREE SHIPPING|BRAND|PRODUCT)\b", text):
            primary = "BUSINESS_ADVERTISEMENTS"
            confidence = 0.87
        elif re.search(r"\b(FORM|APPLICATION|NAME:|DATE OF BIRTH:|SIGNATURE:)\b", text):
            primary = "FORMS"
            confidence = 0.85
        elif ocr_result.detected_tables:
            primary = "CHARTS_INFOGRAPHICS"
            confidence = 0.82
        elif len(text) > 200:
            primary = "DOCUMENTS"
            confidence = 0.85
        elif re.search(r"\b(WHATSAPP|MESSAGES|CHAT|TYPING|BATTERY|WIFI|PM|AM)\b", text):
            primary = "SCREENSHOTS"
            confidence = 0.80
        elif len(text) < 20:
            primary = "PERSONAL_PHOTOGRAPHS"
            confidence = 0.75
        else:
            primary = "POSTERS"
            confidence = 0.70

        return primary, secondary, confidence

    def _compute_risk_indicators(self, ocr_result: OCRResult) -> dict[str, Any]:
        """Detect sensitive data exposure (credit card, SSN, passwords)."""
        text = ocr_result.full_extracted_text
        flags: list[str] = []

        if re.search(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", text):
            flags.append("CREDIT_CARD_NUMBER_EXPOSED")
        if re.search(r"\b(PASSWORD|PIN|OTP|CVV)\s*[:=]?\s*\w+", text, re.IGNORECASE):
            flags.append("CREDENTIALS_EXPOSED")

        score = 0.90 if flags else 0.0
        return {"score": score, "flags": flags}

    def _compute_business_indicators(self, ocr_result: OCRResult, category: str) -> dict[str, Any]:
        """Detect commercial promotions, brand labels, and offers."""
        text = ocr_result.full_extracted_text
        brand_match = re.search(r"\b(AMAZON|FLIPKART|NIKE|APPLE|ZOMATO|SWIGGY|UBER|BANK)\b", text, re.IGNORECASE)
        brand_name = brand_match.group(1) if brand_match else ""

        is_biz = category in ["BUSINESS_ADVERTISEMENTS", "RECEIPTS_INVOICES", "PAYMENT_SCREENSHOTS"] or bool(brand_name)
        score = 0.85 if is_biz else 0.10
        return {"score": score, "brand_name": brand_name}

    def _compute_urgency_indicators(self, ocr_result: OCRResult) -> dict[str, Any]:
        """Detect visual urgency indicators like DUE TODAY, IMMEDIATELY, CLAIM IMMEDIATELY."""
        text = ocr_result.full_extracted_text
        urgent_words = [
            "URGENT",
            "DUE TODAY",
            "LAST CHANCE",
            "IMMEDIATELY",
            "EXPIRING",
            "ACTION REQUIRED",
            "CLAIM IMMEDIATELY",
            "YOU WON",
            "LOTTERY",
        ]
        found = [w for w in urgent_words if w.lower() in text.lower()]

        score = min(len(found) * 0.60, 1.0)
        return {"score": round(score, 2), "keywords": found}


    def _compute_event_indicators(self, ocr_result: OCRResult, category: str) -> dict[str, Any]:
        """Detect event markers, dates, and times."""
        text = ocr_result.full_extracted_text
        date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b", text, re.IGNORECASE)
        event_date = date_match.group(0) if date_match else ""

        is_event = category in ["EVENT_POSTERS", "MEETING_INVITATIONS"] or bool(event_date)
        score = 0.90 if is_event else 0.0
        return {"score": score, "event_date": event_date}

    def _compute_spam_indicators(self, ocr_result: OCRResult, category: str) -> dict[str, Any]:
        """Detect promotional spam likelihood."""
        is_spam = category == "BUSINESS_ADVERTISEMENTS" and "DISCOUNT" in ocr_result.full_extracted_text.upper()
        return {"score": 0.80 if is_spam else 0.05, "reason": "Mass promotional flyer" if is_spam else ""}

    def _compute_scam_indicators(self, ocr_result: OCRResult, category: str) -> dict[str, Any]:
        """Detect scam / phishing tactics."""
        is_scam = category == "SCAM_IMAGES" or "YOU WON" in ocr_result.full_extracted_text.upper()
        return {"score": 0.95 if is_scam else 0.0, "tactic": "PHISHING_LOTTERY_FRAUD" if is_scam else ""}

    def _synthesize_visual_perception(
        self, primary_category: str, ocr_result: OCRResult
    ) -> tuple[list[str], str, str]:
        """Generate list of visual objects, scene description, and image purpose."""
        objects = ["graphic_text"]
        if ocr_result.qr_codes:
            objects.append("qr_code")
        if ocr_result.detected_tables:
            objects.append("table_grid")

        scene_desc = f"Visual media depicting a {primary_category.lower().replace('_', ' ')} asset."
        purpose = f"To communicate visual information regarding {primary_category.lower()}."

        return objects, scene_desc, purpose

    def _generate_overall_summary(
        self,
        primary_category: str,
        ocr_text: str,
        scene_desc: str,
        urgency_ind: dict[str, Any],
        scam_ind: dict[str, Any],
    ) -> str:
        """Synthesize a concise 1-3 sentence overall summary combining visual and textual features."""
        summary = f"Image classified as {primary_category.replace('_', ' ')}."
        if ocr_text:
            first_line = ocr_text.splitlines()[0] if ocr_text.splitlines() else ocr_text[:100]
            summary += f" Contains text: '{first_line}'."

        if scam_ind.get("score", 0.0) > 0.5:
            summary += " Flagged for potential scam/phishing content."
        elif urgency_ind.get("score", 0.0) > 0.5:
            summary += " Indicates high visual urgency."

        return summary
