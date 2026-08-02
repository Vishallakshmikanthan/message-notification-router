"""Decision Intelligence Layer Data Models as specified in decision_models.md.

All data structures are strictly typed and immutable (frozen=True) after
instantiation to guarantee thread safety and audit compliance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import EvidenceBundle
from router.domain.entities.signal import SignalBundle

# ---------------------------------------------------------------------------
# Primary Action & Category Enums
# ---------------------------------------------------------------------------


class DecisionAction(StrEnum):
    """Final routing operation executed by the client notification layer.

    Maps directly to the architecture specification DecisionAction enum.
    """

    DELIVER_IMMEDIATELY = "DELIVER_IMMEDIATELY"
    """High-priority immediate notification with sound, vibration, and banner."""

    DELIVER_SILENT = "DELIVER_SILENT"
    """Deliver notification to shade immediately without audio/haptic interruption."""

    SUMMARIZE_LATER = "SUMMARIZE_LATER"
    """Suppress banner; add to periodic notification summary roll-up."""

    BATCH_DIGEST = "BATCH_DIGEST"
    """Suppress banner; hold for scheduled morning/evening digest batch."""

    SUPPRESS_SPAM = "SUPPRESS_SPAM"
    """Silent suppression; flag as potential spam/phishing in app registry."""

    SUPPRESS_MUTE = "SUPPRESS_MUTE"
    """Complete silent suppression due to explicit user chat/group mute."""

    TRIGGER_EMERGENCY_OVERRIDE = "TRIGGER_EMERGENCY_OVERRIDE"
    """Critical override: force sound/ring tone even during Do-Not-Disturb mode."""


class DecisionCategory(StrEnum):
    """Contextual domain categorization for the notification decision."""

    PERSONAL_URGENT = "PERSONAL_URGENT"
    """High urgency personal message from close contact/family."""

    PERSONAL_CASUAL = "PERSONAL_CASUAL"
    """Non-urgent personal chatter."""

    WORK_CRITICAL = "WORK_CRITICAL"
    """Time-sensitive work communication or project alert."""

    WORK_ROUTINE = "WORK_ROUTINE"
    """General work discussion or group message."""

    TRANSACTIONAL = "TRANSACTIONAL"
    """Bank alert, flight status, OTP code, delivery receipt."""

    MARKETING_PROMO = "MARKETING_PROMO"
    """Promotional offer, vendor deal, broadcast campaign."""

    SAFETY_SECURITY = "SAFETY_SECURITY"
    """Fraud alert, unauthorized login attempt, threat warning."""

    SPAM_VIRAL = "SPAM_VIRAL"
    """Unsolicited broadcast, chain letter, suspicious link bundle."""


# ---------------------------------------------------------------------------
# Supporting sub-structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionParameters:
    """Device notification execution properties controlling presentation layer."""

    play_sound: bool = True
    """Enable alert ringtone/chime."""

    vibrate: bool = True
    """Enable haptic pattern."""

    banner_style: str = "HEADS_UP"
    """One of: HEADS_UP, SILENT_SHADE, SUMMARY_CARD, NONE."""

    scheduled_time: str | None = None
    """ISO-8601 timestamp if action is BATCH_DIGEST or SUMMARIZE_LATER."""

    priority_level: int = 5
    """Android/iOS notification priority channel (1=low, 10=critical)."""


@dataclass(frozen=True)
class LatencyBreakdown:
    """Per-stage execution timing breakdown in milliseconds."""

    preprocessing_ms: float = 0.0
    rule_engine_ms: float = 0.0
    llm_reasoner_ms: float = 0.0
    confidence_calc_ms: float = 0.0
    validation_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass(frozen=True)
class ConfidenceBreakdown:
    """Detailed decomposition of how the final confidence score was computed."""

    raw_llm_confidence: float = 0.0
    """Self-assessed raw confidence from the LLM (0.0–1.0) or 1.0 for rules."""

    signal_agreement_factor: float = 0.0
    """Adjustment applied for signal agreement/disagreement (-0.40 to +0.25)."""

    evidence_relevance_factor: float = 0.0
    """Adjustment applied for evidence grounding quality (-0.30 to 0.0)."""

    history_adjustment_factor: float = 0.0
    """Adjustment applied for historical context completeness (-0.10 to 0.0)."""

    calibrated_confidence: float = 0.0
    """Final post-calibration score after temperature scaling (0.0–1.0)."""


@dataclass(frozen=True)
class VerificationStatus:
    """Flags tracking the 5-pass output validation results."""

    schema_valid: bool = True
    grounding_verified: bool = True
    consistency_verified: bool = True
    fallback_applied: bool = False
    fallback_reason: str | None = None
    grounding_warning: bool = False


@dataclass(frozen=True)
class DecisionMetadata:
    """Telemetry, calibration metrics, latency tracing, and verification flags."""

    execution_id: str = ""
    """UUID for distributed trace correlation."""

    model_version: str = "llm-router-v2.4.1"
    """Version tag of the LLM reasoner model used."""

    latency_breakdown: LatencyBreakdown = field(default_factory=LatencyBreakdown)
    confidence_breakdown: ConfidenceBreakdown = field(default_factory=ConfidenceBreakdown)
    verification_status: VerificationStatus = field(default_factory=VerificationStatus)

    audit_hash: str = ""
    """SHA-256 hash of (context_id + decision_id + action) for tamper-proof logging."""

    decision_path: str = "STANDARD_PATH"
    """FAST_PATH, STANDARD_PATH, FALLBACK_PATH."""


# ---------------------------------------------------------------------------
# DecisionContext — root input wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionContext:
    """Root immutable input wrapper supplied to the Decision Engine.

    Aggregates all upstream layer outputs into a single, normalized,
    validated evaluation frame as specified in decision_models.md §3.
    """

    context_id: str
    """Unique identifier for this decision invocation frame (UUID v4)."""

    timestamp: str
    """ISO-8601 UTC timestamp of context construction."""

    message_context: MessageContext
    """Extracted text payload, chat metadata, and structural features."""

    signal_bundle: SignalBundle
    """Aggregated numerical and categorical signals."""

    evidence_bundle: EvidenceBundle
    """Top retrieved grounded context snippets."""

    media_context: Any | None = None
    """Multimodal analysis metadata (image/voice context if present)."""

    historical_context: Any | None = None
    """Recent 7-day interaction velocity, missed calls, response patterns."""

    business_context: Any | None = None
    """Verified business metadata, campaign IDs, transactional tags."""

    user_context: Any | None = None
    """User current active status, quiet hours rules, address book status."""

    preprocessing_latency_ms: float = 0.0
    """Time taken to assemble this DecisionContext."""


# ---------------------------------------------------------------------------
# RuleEvaluationResult — RuleEngine output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleEvaluationResult:
    """Output produced by the RuleEngine after evaluating the deterministic rule set.

    Spec: decision_models.md §6 Supporting Data Objects.
    """

    rule_fired: bool
    """Indicates whether a deterministic rule matched."""

    rule_id: str | None = None
    """Identifier of the fired rule (e.g., 'RULE_OTP_BYPASS_001')."""

    action: DecisionAction | None = None
    """Action assigned by the rule."""

    category: DecisionCategory | None = None
    """Category classification assigned by the rule."""

    priority: int = 0
    """Priority level (0–100)."""

    bypass_llm: bool = False
    """True if rule short-circuits LLM evaluation."""

    confidence: float = 0.0
    """Confidence in the rule-based decision (0.95–1.0 for Level 0/1)."""

    reasoning_summary: str = ""
    """Human-readable explanation of the rule that fired."""


# ---------------------------------------------------------------------------
# ReasonerInputFrame — payload sent to LLM
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceSnippet:
    """Compact evidence snippet injected into the LLM context frame."""

    evidence_id: str
    text_snippet: str
    relevance_score: float
    source_type: str  # CONVERSATION_HISTORY, CALENDAR, REFERENCE


@dataclass(frozen=True)
class ReasonerInputFrame:
    """Structured context frame consumed by the LLM ReasoningService.

    Prompt-free specification: all inputs are typed, no raw prompt strings.
    Spec: decision_engine.md §5 LLM Reasoner Architecture.
    """

    # Message payload
    message_text: str
    message_type: str
    language_code: str
    char_count: int

    # Aggregated signals (normalized floats)
    urgency_score: float
    spam_score: float
    trust_score: float
    relationship_closeness: float
    sentiment_score: float

    # Quiet hours & user state
    is_quiet_hours: bool
    user_activity_status: str  # AVAILABLE, IN_MEETING, DRIVING, SLEEPING

    # Sender relationship tier
    sender_is_vip: bool
    sender_in_address_book: bool
    sender_relationship_type: str

    # Temporal context
    local_time_iso: str
    day_of_week: str
    hour_of_day: int

    # Evidence grounding (top-5 snippets)
    evidence_snippets: list[EvidenceSnippet] = field(default_factory=list)

    # Media context (optional)
    has_media: bool = False
    media_type: str = "TEXT_ONLY"
    media_summary: str = ""
    media_risk_score: float = 0.0

    # Historical context
    historical_response_latency_seconds: float = 0.0
    missed_calls_from_sender: int = 0
    historical_open_rate: float = 0.0


# ---------------------------------------------------------------------------
# ReasoningOutput — LLM response payload
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReasoningOutput:
    """Strictly typed output from the LLM ReasoningService.

    Spec: decision_engine.md §5 Structural Outputs.
    """

    proposed_action: DecisionAction
    """Recommended routing action."""

    urgency_rating: float
    """Normalized urgency float (0.0–1.0)."""

    importance_rating: float
    """Normalized importance float (0.0–1.0)."""

    reasoning_summary: str
    """Concise natural language explanation (max 250 chars)."""

    key_factors: list[str]
    """Primary factors driving the recommendation."""

    raw_confidence: float
    """Model self-assessed confidence score (0.0–1.0)."""

    proposed_category: DecisionCategory = DecisionCategory.PERSONAL_CASUAL
    """Suggested message domain category."""

    evidence_ids_referenced: list[str] = field(default_factory=list)
    """Evidence IDs cited in the reasoning summary."""

    llm_latency_ms: float = 0.0
    """Wall-clock LLM invocation latency."""


# ---------------------------------------------------------------------------
# CalibratedDecision — post-confidence-engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibratedDecision:
    """Decision output after ConfidenceEngine calibration.

    Carries both the proposed action and a well-calibrated posterior confidence.
    """

    action: DecisionAction
    category: DecisionCategory
    urgency_score: float
    importance_score: float
    reasoning_summary: str
    key_factors: list[str]
    evidence_ids: list[str]

    calibrated_confidence: float
    confidence_breakdown: ConfidenceBreakdown

    bypassed_llm: bool = False
    triggered_rule_id: str | None = None
    grounding_warning: bool = False


# ---------------------------------------------------------------------------
# VerificationResult — DecisionValidator output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationResult:
    """Multi-pass validation output from DecisionValidator.

    Spec: decision_models.md §6 Supporting Data Objects.
    """

    is_valid: bool
    """True if decision passed all 5 validation gates."""

    validation_errors: list[str] = field(default_factory=list)
    """List of specific validation failure descriptions."""

    suggested_fallback_action: DecisionAction | None = None
    """Safe fallback action if any validation gate failed."""

    passes_executed: int = 0
    """Number of validation passes executed (max 5)."""


# ---------------------------------------------------------------------------
# DecisionResult — final validated output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionResult:
    """Final validated output payload returned by the Decision Engine.

    Spec: decision_models.md §4 Schema: DecisionResult.
    """

    decision_id: str
    """Unique execution ID for tracing (UUID v4)."""

    context_id: str
    """References the corresponding DecisionContext.context_id."""

    action: DecisionAction
    """Final notification routing action."""

    urgency_score: float
    """Calibrated message urgency level (0.0–1.0)."""

    importance_score: float
    """Calibrated message importance level (0.0–1.0)."""

    category: DecisionCategory
    """Primary message domain classification."""

    reasoning_summary: str
    """Structured natural language explanation (max 250 chars)."""

    triggered_rule_id: str | None
    """Rule ID if deterministic rule fired; None if LLM was used."""

    bypassed_llm: bool
    """True if RuleEngine short-circuited LLM."""

    action_params: ActionParameters
    """Client presentation instructions (sound, vibration, banner)."""

    metadata: DecisionMetadata
    """Latency, confidence breakdown, audit hashes."""

    evidence_ids: list[str] = field(default_factory=list)
    """IDs of evidence items grounding the reasoning."""

    def compute_audit_hash(self) -> str:
        """Compute SHA-256 hash of key fields for tamper-proof logging."""
        payload = json.dumps(
            {
                "context_id": self.context_id,
                "decision_id": self.decision_id,
                "action": str(self.action),
                "urgency_score": self.urgency_score,
                "calibrated_confidence": self.metadata.confidence_breakdown.calibrated_confidence,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Utility: default ActionParameters per action
# ---------------------------------------------------------------------------

_ACTION_PARAMS_MAP: dict[DecisionAction, ActionParameters] = {
    DecisionAction.DELIVER_IMMEDIATELY: ActionParameters(
        play_sound=True, vibrate=True, banner_style="HEADS_UP", priority_level=9
    ),
    DecisionAction.DELIVER_SILENT: ActionParameters(
        play_sound=False, vibrate=False, banner_style="SILENT_SHADE", priority_level=4
    ),
    DecisionAction.SUMMARIZE_LATER: ActionParameters(
        play_sound=False, vibrate=False, banner_style="SUMMARY_CARD", priority_level=2
    ),
    DecisionAction.BATCH_DIGEST: ActionParameters(
        play_sound=False, vibrate=False, banner_style="SUMMARY_CARD", priority_level=1
    ),
    DecisionAction.SUPPRESS_SPAM: ActionParameters(
        play_sound=False, vibrate=False, banner_style="NONE", priority_level=0
    ),
    DecisionAction.SUPPRESS_MUTE: ActionParameters(
        play_sound=False, vibrate=False, banner_style="NONE", priority_level=0
    ),
    DecisionAction.TRIGGER_EMERGENCY_OVERRIDE: ActionParameters(
        play_sound=True, vibrate=True, banner_style="HEADS_UP", priority_level=10
    ),
}


def build_action_params(action: DecisionAction, scheduled_time: str | None = None) -> ActionParameters:
    """Build default ActionParameters for a given DecisionAction.

    Args:
        action: The routing action.
        scheduled_time: Optional ISO-8601 timestamp for batch/summary actions.

    Returns:
        Appropriate ActionParameters instance.
    """
    base = _ACTION_PARAMS_MAP.get(action, ActionParameters())
    if scheduled_time and action in (DecisionAction.BATCH_DIGEST, DecisionAction.SUMMARIZE_LATER):
        # Return new instance with scheduled_time injected
        return ActionParameters(
            play_sound=base.play_sound,
            vibrate=base.vibrate,
            banner_style=base.banner_style,
            priority_level=base.priority_level,
            scheduled_time=scheduled_time,
        )
    return base
