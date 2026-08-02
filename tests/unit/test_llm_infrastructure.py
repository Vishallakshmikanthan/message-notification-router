"""Unit tests for Phase 8 Output Parser, JSON Validator, and Retry Manager."""

import pytest

from router.infrastructure.llm.json_validator import JSONValidator
from router.infrastructure.llm.output_parser import OutputParser
from router.infrastructure.llm.retry_manager import MaxRetriesExceededError, RetryManager


def test_output_parser_clean():
    parser = OutputParser()
    raw = '{"action": "NOTIFY_IMMEDIATELY", "reason": "Urgent alert", "confidence": 0.9, "evidence": ["key1"]}'
    res = parser.parse(raw)
    assert res.action == "NOTIFY_IMMEDIATELY"
    assert res.confidence == 0.9
    assert res.reason == "Urgent alert"
    assert not res.repair_applied


def test_output_parser_markdown_fence():
    parser = OutputParser()
    raw = '```json\n{"action": "DELIVER_SILENTLY", "reason": "Low priority", "confidence": 0.7, "evidence": []}\n```'
    res = parser.parse(raw)
    assert res.action == "DELIVER_SILENTLY"
    assert res.confidence == 0.7
    assert res.repair_applied


def test_json_validator():
    validator = JSONValidator(context_evidence_keys=["key1", "key2"])
    data = {
        "action": "notify_immediately",
        "reason": "Valid reason",
        "confidence": "0.85",
        "evidence": ["key1"],
    }
    res = validator.validate(data)
    assert res.is_valid
    assert res.validated_data["action"] == "NOTIFY_IMMEDIATELY"
    assert res.validated_data["confidence"] == 0.85


def test_json_validator_hallucination():
    validator = JSONValidator(context_evidence_keys=["key1"])
    data = {
        "action": "DELIVER_SILENTLY",
        "reason": "Test",
        "confidence": 0.5,
        "evidence": ["hallucinated_key"],
    }
    res = validator.validate(data)
    assert "hallucinated_key" in res.hallucinated_keys


def test_retry_manager_success():
    rm = RetryManager(max_retries=2, base_backoff_ms=10)
    count = 0

    def work():
        nonlocal count
        count += 1
        if count < 2:
            raise ValueError("Transient error")
        return "OK"

    res = rm.execute(work)
    assert res.success
    assert res.value == "OK"
    assert res.attempt_count >= 1


def test_retry_manager_exceeded():
    rm = RetryManager(max_retries=2, base_backoff_ms=5)

    def work():
        raise ValueError("Persistent error")

    with pytest.raises(MaxRetriesExceededError):
        rm.execute(work)
