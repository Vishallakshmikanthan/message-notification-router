"""ConfidenceEngine — Confidence calculation, calibration, and uncertainty management.

Implements the full mathematical formulation from confidence_engine.md:

  C_base = C_raw + S_adj + E_adj + H_adj

Then applies temperature-scaled sigmoid calibration (Platt Scaling):

  C_calibrated = sigmoid(logit(C_base) / T)

Enforces action-specific minimum confidence thresholds (§5 Dynamic Thresholding).
If calibrated confidence falls below action threshold, automatically downgrades
to the specified safe fallback action.

Spec: confidence_engine.md §2-§6.
"""

from __future__ import annotations

import math
from typing import List, Optional

from router.core.logging.logger import get_logger
from router.domain.entities.decision_models import (
    CalibratedDecision,
    ConfidenceBreakdown,
    DecisionAction,
    DecisionCategory,
    DecisionContext,
    RuleEvaluationResult,
    ReasoningOutput,
)
from router.domain.ports.decision_ports import IConfidenceEngine

logger = get_logger(__name__)

# Temperature parameter for Platt scaling (tuned empirically: 1.35–1.50)
_TEMPERATURE_T = 1.40

# Signal agreement adjustment bounds
_S_ADJ_AGREE_MAX = +0.25
_S_ADJ_AGREE_MIN = +0.15
_S_ADJ_DISAGREE_MAX = -0.20
_S_ADJ_DISAGREE_MIN = -0.40

# Evidence adjustment bounds
_E_ADJ_WEAK_MIN = -0.15
_E_ADJ_WEAK_MAX = -0.30

# History adjustment
_H_ADJ_MISSING = -0.10

# Media corruption penalty
_M_ADJ_CORRUPT = -0.15

# Minimum calibrated_confidence floor
_CONFIDENCE_FLOOR = 0.05
_CONFIDENCE_CEIL = 0.97

# Action-specific minimum confidence thresholds (confidence_engine.md §5)
_ACTION_MIN_CONFIDENCE = {
    DecisionAction.TRIGGER_EMERGENCY_OVERRIDE: 0.90,
    DecisionAction.DELIVER_IMMEDIATELY: 0.70,
    DecisionAction.SUPPRESS_SPAM: 0.85,
    DecisionAction.SUMMARIZE_LATER: 0.55,
    DecisionAction.DELIVER_SILENT: 0.45,
    DecisionAction.BATCH_DIGEST: 0.35,
    DecisionAction.SUPPRESS_MUTE: 0.80,
}

# Fallback actions when threshold is not met (confidence_engine.md §5)
_ACTION_FALLBACK = {
    DecisionAction.TRIGGER_EMERGENCY_OVERRIDE: DecisionAction.DELIVER_IMMEDIATELY,
    DecisionAction.DELIVER_IMMEDIATELY: DecisionAction.DELIVER_SILENT,
    DecisionAction.SUPPRESS_SPAM: DecisionAction.DELIVER_SILENT,
    DecisionAction.SUMMARIZE_LATER: DecisionAction.BATCH_DIGEST,
    DecisionAction.DELIVER_SILENT: DecisionAction.BATCH_DIGEST,
}


class ConfidenceEngine(IConfidenceEngine):
    """Calibrates posterior confidence for notification routing decisions.

    Applies four adjustment factors then temperature-scale sigmoid calibration:
    1. Signal Agreement Factor (S_adj)
    2. Evidence Relevance Factor (E_adj)
    3. Historical Context Factor (H_adj)
    4. Temperature Scaling (Platt Model)

    Enforces minimum threshold requirements per action type, automatically
    downgrading to safe fallbacks when confidence is insufficient.
    """

    def __init__(self, temperature: float = _TEMPERATURE_T) -> None:
        """Initialize with configurable temperature parameter.

        Args:
            temperature: Platt scaling temperature T (default 1.40).
        """
        self._temperature = temperature
        logger.info("ConfidenceEngine initialized", temperature=temperature)

    def calibrate(
        self,
        rule_result: Optional[RuleEvaluationResult],
        reasoning_output: Optional[ReasoningOutput],
        context: DecisionContext,
    ) -> CalibratedDecision:
        """Compute calibrated posterior confidence from raw inputs.

        Decision path:
        - If rule_result.rule_fired: use rule confidence (1.0 for Level 0, 0.95 for Level 1).
        - If reasoning_output: compute full calibration pipeline.

        Args:
            rule_result: Non-None if deterministic rule fired.
            reasoning_output: Non-None if LLM path was executed.
            context: Full DecisionContext for signal agreement analysis.

        Returns:
            CalibratedDecision with posterior confidence and full breakdown.
        """
        sb = context.signal_bundle
        eb = context.evidence_bundle

        # ---- Extract raw decision fields --------------------------------
        if rule_result and rule_result.rule_fired:
            c_raw = rule_result.confidence
            action = rule_result.action or DecisionAction.DELIVER_SILENT
            category = rule_result.category or DecisionCategory.PERSONAL_CASUAL
            urgency_score = sb.urgency_score
            importance_score = sb.trust.relationship_score.score
            reasoning_summary = rule_result.reasoning_summary or ""
            key_factors = [rule_result.rule_id or "DETERMINISTIC_RULE"]
            evidence_ids = sb.candidate_evidence_ids[:5]
            bypassed_llm = True
            triggered_rule_id = rule_result.rule_id

        elif reasoning_output:
            c_raw = reasoning_output.raw_confidence
            action = reasoning_output.proposed_action
            category = reasoning_output.proposed_category
            urgency_score = reasoning_output.urgency_rating
            importance_score = reasoning_output.importance_rating
            reasoning_summary = reasoning_output.reasoning_summary
            key_factors = reasoning_output.key_factors
            evidence_ids = reasoning_output.evidence_ids_referenced or sb.candidate_evidence_ids[:5]
            bypassed_llm = False
            triggered_rule_id = None

        else:
            # Fallback: no rule, no LLM output — apply system default
            logger.warning(
                "ConfidenceEngine received neither rule nor reasoning output; applying fallback.",
                context_id=context.context_id,
            )
            return self._build_fallback_decision(context, "NO_INPUT")

        # ---- Compute adjustment factors ----------------------------------
        s_adj = self._compute_signal_agreement(sb)
        e_adj = self._compute_evidence_adjustment(eb)
        h_adj = self._compute_history_adjustment(context)

        # ---- Base confidence (clamped before calibration) ----------------
        c_base = c_raw + s_adj + e_adj + h_adj
        c_base = max(_CONFIDENCE_FLOOR, min(_CONFIDENCE_CEIL, c_base))

        # ---- Temperature scaling (Platt sigmoid) -------------------------
        c_calibrated = self._sigmoid_calibrate(c_base)

        # ---- Grounding warning check -------------------------------------
        top_evidence_relevance = max(
            (item.similarity_score for item in eb.items), default=0.0
        )
        grounding_warning = False
        if top_evidence_relevance < 0.40 and not bypassed_llm:
            # Low-quality evidence penalty already included in e_adj
            grounding_warning = True

        # ---- Quiet hours DELIVER_IMMEDIATELY requires higher threshold ---
        if action == DecisionAction.DELIVER_IMMEDIATELY and sb.is_quiet_hours:
            required = 0.85
        else:
            required = _ACTION_MIN_CONFIDENCE.get(action, 0.35)

        # ---- Threshold enforcement & downgrade --------------------------
        if c_calibrated < required:
            fallback_action = _ACTION_FALLBACK.get(action, DecisionAction.DELIVER_SILENT)
            logger.info(
                "Confidence below action threshold; downgrading action",
                original_action=action,
                fallback_action=fallback_action,
                calibrated_confidence=round(c_calibrated, 3),
                required_threshold=required,
            )
            action = fallback_action

        # ---- Build breakdown --------------------------------------------
        breakdown = ConfidenceBreakdown(
            raw_llm_confidence=c_raw,
            signal_agreement_factor=round(s_adj, 4),
            evidence_relevance_factor=round(e_adj, 4),
            history_adjustment_factor=round(h_adj, 4),
            calibrated_confidence=round(c_calibrated, 4),
        )

        logger.info(
            "Confidence calibrated",
            context_id=context.context_id,
            c_raw=round(c_raw, 3),
            s_adj=round(s_adj, 3),
            e_adj=round(e_adj, 3),
            h_adj=round(h_adj, 3),
            c_calibrated=round(c_calibrated, 3),
            final_action=action,
            bypassed_llm=bypassed_llm,
        )

        return CalibratedDecision(
            action=action,
            category=category,
            urgency_score=min(1.0, max(0.0, urgency_score)),
            importance_score=min(1.0, max(0.0, importance_score)),
            reasoning_summary=reasoning_summary[:250],
            key_factors=key_factors,
            evidence_ids=evidence_ids,
            calibrated_confidence=round(c_calibrated, 4),
            confidence_breakdown=breakdown,
            bypassed_llm=bypassed_llm,
            triggered_rule_id=triggered_rule_id,
            grounding_warning=grounding_warning,
        )

    # ------------------------------------------------------------------
    # Adjustment factor computations
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_signal_agreement(sb) -> float:
        """Compute S_adj: signal agreement/disagreement adjustment.

        High agreement (all signals point same direction): +0.15 to +0.25.
        Severe contradiction (e.g., high urgency + low trust): -0.20 to -0.40.

        Args:
            sb: SignalBundle.

        Returns:
            Float adjustment value.
        """
        urgency = sb.urgency_score
        trust = sb.trust.relationship_score.score
        spam = sb.risk.spam.score

        # Severe contradiction: high urgency + low trust
        if urgency > 0.85 and trust < 0.30:
            return _S_ADJ_DISAGREE_MAX  # -0.40

        # Contradiction: spam HIGH + VIP sender
        if spam > 0.70 and trust >= 0.85:
            return _S_ADJ_DISAGREE_MIN  # -0.20

        # Compute signal std_dev for agreement scoring
        scores = [urgency, trust, 1.0 - spam]  # spam inverted for direction
        mean_score = sum(scores) / len(scores)
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        std_dev = math.sqrt(variance)

        if std_dev < 0.10:
            return _S_ADJ_AGREE_MAX   # +0.25 — very high agreement
        elif std_dev < 0.15:
            return _S_ADJ_AGREE_MIN   # +0.15 — moderate agreement
        elif std_dev < 0.25:
            return 0.0                # Neutral — weak disagreement
        else:
            return _S_ADJ_DISAGREE_MIN  # -0.20 — significant disagreement

    @staticmethod
    def _compute_evidence_adjustment(eb) -> float:
        """Compute E_adj: evidence grounding quality adjustment.

        Missing/weak evidence: -0.15 to -0.30.
        Strong evidence: 0.0 (no positive bonus — that comes from S_adj).

        Args:
            eb: EvidenceBundle.

        Returns:
            Float adjustment value (negative or zero).
        """
        if eb.evidence_count == 0 or not eb.items:
            return _E_ADJ_WEAK_MAX  # -0.30 — zero evidence

        top_relevance = max(item.similarity_score for item in eb.items)

        if top_relevance < 0.20:
            return _E_ADJ_WEAK_MAX    # -0.30 — very low relevance
        elif top_relevance < 0.40:
            return _E_ADJ_WEAK_MIN    # -0.15 — below threshold
        else:
            return 0.0                # Acceptable evidence quality

    @staticmethod
    def _compute_history_adjustment(context: DecisionContext) -> float:
        """Compute H_adj: historical context completeness adjustment.

        Missing history (cold-start, new sender): -0.10.

        Args:
            context: DecisionContext.

        Returns:
            Float adjustment value (-0.10 or 0.0).
        """
        sb = context.signal_bundle
        hist_open = sb.history.historical_open_rate.score
        hist_reply = sb.history.historical_reply_rate.score

        # Cold-start: no historical interaction data
        if hist_open == 0.0 and hist_reply == 0.0:
            return _H_ADJ_MISSING  # -0.10

        return 0.0

    def _sigmoid_calibrate(self, c_base: float) -> float:
        """Apply temperature-scaled sigmoid calibration (Platt Scaling).

        Formula: C_calibrated = 1 / (1 + exp(-logit(C_base) / T))

        Args:
            c_base: Uncalibrated base confidence (0.0–1.0).

        Returns:
            Calibrated posterior confidence (0.0–1.0).
        """
        # Clamp to avoid log(0) / log(1) singularities
        c_clamped = max(0.001, min(0.999, c_base))
        logit_val = math.log(c_clamped / (1.0 - c_clamped))
        scaled_logit = logit_val / self._temperature
        calibrated = 1.0 / (1.0 + math.exp(-scaled_logit))
        return max(_CONFIDENCE_FLOOR, min(_CONFIDENCE_CEIL, calibrated))

    def _build_fallback_decision(self, context: DecisionContext, reason: str) -> CalibratedDecision:
        """Build a safe default CalibratedDecision for system recovery scenarios.

        Args:
            context: DecisionContext.
            reason: Fallback reason code for logging.

        Returns:
            CalibratedDecision with DELIVER_SILENT and confidence=0.50.
        """
        sb = context.signal_bundle
        action = (
            DecisionAction.DELIVER_SILENT
            if sb.personal_sender_known
            else DecisionAction.SUMMARIZE_LATER
        )

        logger.warning(
            "ConfidenceEngine applying safe fallback",
            reason=reason,
            context_id=context.context_id,
            fallback_action=action,
        )

        breakdown = ConfidenceBreakdown(
            raw_llm_confidence=0.50,
            signal_agreement_factor=0.0,
            evidence_relevance_factor=0.0,
            history_adjustment_factor=0.0,
            calibrated_confidence=0.50,
        )

        return CalibratedDecision(
            action=action,
            category=DecisionCategory.PERSONAL_CASUAL,
            urgency_score=0.50,
            importance_score=0.50,
            reasoning_summary=f"System applied safe default: {reason}.",
            key_factors=[reason],
            evidence_ids=[],
            calibrated_confidence=0.50,
            confidence_breakdown=breakdown,
            bypassed_llm=False,
            triggered_rule_id=None,
        )
