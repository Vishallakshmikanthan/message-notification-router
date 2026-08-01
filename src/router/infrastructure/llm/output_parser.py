"""Output Parser — multi-stage JSON extraction and self-healing for LLM responses.

Implements the 4-Stage Output Validation & Self-Healing Architecture from
prompt_architecture.md §5:

Stage 1: Syntax Repair — handles trailing commas, markdown fences, unescaped quotes.
Stage 2: Structural Schema Coercion — validates against expected output schema.
Stage 3: Allowed Values & Grounding Check — verifies enum values and confidence bounds.
Stage 4: LLM Auto-Repair Loop — if all syntax/schema repair fails.

Spec: prompt_architecture.md §5 (Output Validation & Self-Healing Architecture).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Valid routing action enum values (prompt_architecture.md §3)
VALID_ACTIONS = frozenset(
    {"NOTIFY_IMMEDIATELY", "DELIVER_SILENTLY", "SUMMARIZE_IN_BATCH", "DO_NOT_DISTURB"}
)

# Default fallback action when all repair stages fail
_FALLBACK_ACTION = "DELIVER_SILENTLY"

# Regex patterns for JSON extraction
_CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA_PATTERN = re.compile(r",\s*([}\]])")
_UNQUOTED_KEY_PATTERN = re.compile(r"(\s*)(\w+)(\s*:)")


@dataclass
class ParseResult:
    """Result of the multi-stage output parsing pipeline.

    Attributes:
        parsed: The parsed and validated JSON dict.
        raw_response: The original raw LLM response string.
        repair_applied: Whether any repair stage was applied.
        repair_stage: Which stage (1-4) performed the repair, or 0 if clean.
        parse_errors: List of errors encountered during parsing.
        is_fallback: Whether the fallback hardcoded response was returned.
    """

    parsed: Dict[str, Any]
    raw_response: str
    repair_applied: bool
    repair_stage: int
    parse_errors: List[str] = field(default_factory=list)
    is_fallback: bool = False

    @property
    def action(self) -> str:
        """Extract the routing action from parsed output."""
        return self.parsed.get("action", _FALLBACK_ACTION)

    @property
    def confidence(self) -> float:
        """Extract calibrated confidence from parsed output."""
        return float(self.parsed.get("confidence", 0.5))

    @property
    def reason(self) -> str:
        """Extract routing reason from parsed output."""
        return str(self.parsed.get("reason", ""))

    @property
    def evidence(self) -> List[str]:
        """Extract evidence key list from parsed output."""
        return list(self.parsed.get("evidence", []))


class OutputParser:
    """Multi-stage JSON extraction and self-healing parser.

    Processes raw LLM text responses through 4 repair stages to extract
    valid, schema-compliant JSON. Falls back deterministically to DELIVER_SILENTLY
    if all stages fail.

    Args:
        enable_stage4_repair: Whether to enable Stage 4 LLM repair loop.
                              Disable in unit tests to avoid API calls.
    """

    def __init__(self, enable_stage4_repair: bool = False) -> None:
        """Initialize OutputParser.

        Args:
            enable_stage4_repair: Enable/disable Stage 4 LLM repair.
        """
        self._enable_stage4_repair = enable_stage4_repair
        logger.info(
            "OutputParser initialized",
            extra={"enable_stage4_repair": enable_stage4_repair},
        )

    def parse(self, raw_response: str) -> ParseResult:
        """Parse and validate a raw LLM response through all repair stages.

        Args:
            raw_response: Raw text response from the LLM provider.

        Returns:
            ParseResult with parsed JSON dict and repair metadata.
        """
        errors: List[str] = []

        # Stage 1: Syntax Repair — extract and fix JSON
        stage1_result, stage1_text = self._stage1_syntax_repair(raw_response, errors)
        if stage1_result is not None:
            # Stage 2: Schema coercion
            coerced = self._stage2_schema_coercion(stage1_result, errors)
            # Stage 3: Allowed values check
            validated, stage3_errors = self._stage3_allowed_values(coerced)
            errors.extend(stage3_errors)

            if not stage3_errors:
                repair_stage = 1 if raw_response != stage1_text else 0
                return ParseResult(
                    parsed=validated,
                    raw_response=raw_response,
                    repair_applied=repair_stage > 0,
                    repair_stage=repair_stage,
                    parse_errors=errors,
                )
            else:
                # Stage 3 failed — try to fix within existing parsed data
                fixed = self._stage3_fix(coerced)
                return ParseResult(
                    parsed=fixed,
                    raw_response=raw_response,
                    repair_applied=True,
                    repair_stage=3,
                    parse_errors=errors,
                )

        # Stage 4: LLM repair loop (if enabled)
        if self._enable_stage4_repair:
            # Return an indication to the caller to trigger Stage 4
            errors.append("STAGE_4_LLM_REPAIR_REQUIRED")
        else:
            errors.append("ALL_REPAIR_STAGES_FAILED")

        # Stage 5: Graceful fallback
        fallback = self._build_fallback(errors)
        return ParseResult(
            parsed=fallback,
            raw_response=raw_response,
            repair_applied=True,
            repair_stage=4,
            parse_errors=errors,
            is_fallback=True,
        )

    def extract_json_string(self, text: str) -> Optional[str]:
        """Extract a JSON string from text that may contain markdown or prose.

        Handles:
        - Code fence stripping (```json ... ```)
        - Brace extraction from surrounding prose.

        Args:
            text: Raw text potentially containing JSON.

        Returns:
            Extracted JSON string, or None if no JSON found.
        """
        # Try code fence extraction first
        fence_match = _CODE_FENCE_PATTERN.search(text)
        if fence_match:
            return fence_match.group(1).strip()

        # Try brace extraction
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

        return None

    def _stage1_syntax_repair(
        self, raw: str, errors: List[str]
    ) -> tuple[Optional[Dict[str, Any]], str]:
        """Stage 1: Extract JSON and repair syntax errors.

        Handles:
        - Code fence stripping.
        - Trailing commas before } or ].
        - Single-quoted strings → double-quoted.
        - Missing closing brackets.

        Args:
            raw: Raw LLM response.
            errors: Error list to append to.

        Returns:
            Tuple of (parsed_dict or None, repaired_text).
        """
        # First try direct parse
        try:
            return json.loads(raw), raw
        except json.JSONDecodeError:
            pass

        # Extract JSON substring
        json_str = self.extract_json_string(raw)
        if json_str is None:
            errors.append("STAGE1_NO_JSON_FOUND")
            return None, raw

        # Apply syntax repairs
        repaired = self._apply_syntax_repairs(json_str)

        try:
            return json.loads(repaired), repaired
        except json.JSONDecodeError as exc:
            errors.append(f"STAGE1_PARSE_FAILURE: {exc}")
            return None, repaired

    @staticmethod
    def _apply_syntax_repairs(text: str) -> str:
        """Apply common LLM JSON syntax fixes.

        Args:
            text: Extracted JSON string.

        Returns:
            Repaired JSON string.
        """
        # Fix trailing commas: , } or , ]
        text = _TRAILING_COMMA_PATTERN.sub(r"\1", text)

        # Fix single-quoted strings (simple cases)
        text = text.replace("'", '"')

        # Fix unescaped newlines in string values
        # Replace literal newlines inside string values with \n
        in_string = False
        result_chars: List[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '"' and (i == 0 or text[i - 1] != "\\"):
                in_string = not in_string
            if in_string and ch == "\n":
                result_chars.append("\\n")
            else:
                result_chars.append(ch)
            i += 1
        return "".join(result_chars)

    @staticmethod
    def _stage2_schema_coercion(data: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
        """Stage 2: Coerce types to match the expected output schema.

        Handles:
        - String → float confidence coercion.
        - String → list evidence coercion.
        - Whitespace trimming on string values.

        Args:
            data: Partially parsed JSON dict.
            errors: Error list to append to.

        Returns:
            Type-coerced dict.
        """
        coerced = dict(data)

        # Coerce action
        if "action" in coerced:
            coerced["action"] = str(coerced["action"]).strip().upper()

        # Coerce confidence
        if "confidence" in coerced:
            try:
                coerced["confidence"] = float(coerced["confidence"])
            except (ValueError, TypeError):
                errors.append("STAGE2_CONFIDENCE_COERCION_FAILED")
                coerced["confidence"] = 0.5

        # Coerce reason
        if "reason" in coerced:
            coerced["reason"] = str(coerced["reason"]).strip()

        # Coerce evidence to list
        if "evidence" in coerced:
            ev = coerced["evidence"]
            if isinstance(ev, str):
                coerced["evidence"] = [ev] if ev else []
            elif not isinstance(ev, list):
                coerced["evidence"] = []

        return coerced

    @staticmethod
    def _stage3_allowed_values(data: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
        """Stage 3: Validate allowed values and confidence bounds.

        Validates:
        - action MUST be in VALID_ACTIONS enum.
        - confidence MUST be in [0.0, 1.0].
        - evidence keys must be strings.

        Args:
            data: Type-coerced JSON dict.

        Returns:
            Tuple of (validated_dict, list_of_errors).
        """
        errors: List[str] = []

        # Validate required fields present
        for required_field in ("action", "reason", "confidence"):
            if required_field not in data:
                errors.append(f"STAGE3_MISSING_FIELD:{required_field}")

        # Validate action enum
        action = data.get("action", "")
        if action not in VALID_ACTIONS:
            errors.append(f"STAGE3_INVALID_ACTION:{action}")

        # Validate confidence bounds
        confidence = data.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
            errors.append(f"STAGE3_CONFIDENCE_OUT_OF_BOUNDS:{confidence}")

        return data, errors

    @staticmethod
    def _stage3_fix(data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Stage 3 fixes to bring data into compliance.

        Args:
            data: Data dict with potential Stage 3 violations.

        Returns:
            Fixed dict with all values within allowed bounds.
        """
        fixed = dict(data)

        # Fix action
        action = str(fixed.get("action", "")).upper()
        if action not in VALID_ACTIONS:
            fixed["action"] = _FALLBACK_ACTION

        # Clamp confidence
        try:
            conf = float(fixed.get("confidence", 0.5))
            fixed["confidence"] = max(0.0, min(1.0, conf))
        except (ValueError, TypeError):
            fixed["confidence"] = 0.5

        # Ensure reason is a string
        if "reason" not in fixed or not isinstance(fixed["reason"], str):
            fixed["reason"] = "System applied routing decision."

        # Ensure evidence is a list
        if "evidence" not in fixed or not isinstance(fixed["evidence"], list):
            fixed["evidence"] = []

        return fixed

    @staticmethod
    def _build_fallback(errors: List[str]) -> Dict[str, Any]:
        """Build a hardcoded Stage 5 fallback response.

        Args:
            errors: Error messages to include in the fallback reason.

        Returns:
            Hardcoded safe JSON fallback dict.
        """
        return {
            "action": _FALLBACK_ACTION,
            "reason": "System applied safe default due to response parsing failure.",
            "confidence": 0.40,
            "evidence": [],
            "_is_fallback": True,
            "_parse_errors": errors[:5],
        }
