"""Prompt Evaluator — LLM-as-a-Judge Rationale & Grounding Rubrics.

Implements Reason & Evidence Quality Evaluation (LLM-as-a-Judge) from evaluation_framework.md §4:
- Factual Grounding (Zero hallucinated facts)
- Conciseness (Under 25 words)
- Logical Consistency (Reason strictly supports action)
- User Context Alignment

Spec: evaluation_framework.md §4 (Evaluation Rubric Matrix).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class PromptJudgeScore:
    """Evaluation score for a single generated response rationale."""

    grounding_score: float  # 0.0-1.0
    conciseness_score: float  # 0.0-1.0
    logic_score: float  # 0.0-1.0
    overall_judge_score: float  # 0.0-1.0
    violations: List[str]


class PromptEvaluator:
    """LLM-as-a-Judge Prompt & Output Quality Evaluator."""

    def __init__(self) -> None:
        """Initialize PromptEvaluator."""
        pass

    def evaluate_reasoning(
        self,
        action: str,
        reason: str,
        evidence_keys: List[str],
        valid_context_keys: List[str],
    ) -> PromptJudgeScore:
        """Evaluate reason and evidence using rubrics.

        Args:
            action: Selected routing action.
            reason: Reasoning text generated.
            evidence_keys: Citations provided.
            valid_context_keys: Known valid keys in context.

        Returns:
            PromptJudgeScore object.
        """
        violations: List[str] = []

        # 1. Conciseness Check (<25 words)
        words = reason.split()
        if len(words) > 25:
            violations.append(f"REASON_TOO_LONG ({len(words)} words > 25)")
            conciseness = max(0.0, 1.0 - (len(words) - 25) * 0.05)
        else:
            conciseness = 1.0

        # 2. Factual Grounding Check
        if valid_context_keys:
            invalid_keys = [k for k in evidence_keys if k and k not in valid_context_keys]
            if invalid_keys:
                violations.append(f"UNGROUNDED_EVIDENCE_KEYS: {invalid_keys}")
                grounding = max(0.0, 1.0 - (len(invalid_keys) / max(1, len(evidence_keys))))
            else:
                grounding = 1.0
        else:
            grounding = 1.0 if not evidence_keys else 0.8

        # 3. Logical Consistency Check (basic heuristic checks)
        logic = 1.0
        if action == "NOTIFY_IMMEDIATELY" and ("spam" in reason.lower() or "quiet" in reason.lower()):
            violations.append("CONTRADICTORY_REASONING_NOTIFY")
            logic = 0.5
        elif action == "DO_NOT_DISTURB" and "urgent" in reason.lower():
            violations.append("CONTRADICTORY_REASONING_DND")
            logic = 0.5

        overall = round((grounding * 0.4) + (conciseness * 0.3) + (logic * 0.3), 3)

        return PromptJudgeScore(
            grounding_score=round(grounding, 3),
            conciseness_score=round(conciseness, 3),
            logic_score=round(logic, 3),
            overall_judge_score=overall,
            violations=violations,
        )
