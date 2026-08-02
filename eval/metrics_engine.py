"""Metrics Engine — Quantitative Evaluation Metrics for Notification Router.

Implements Core Quantitative Evaluation Metrics from evaluation_framework.md §2 & §3:
1. Multi-Class Classification Performance (Macro F1, Action-Specific Precision & Recall, Weighted Accuracy)
2. Risk-Weighted Error Matrix (Severity cost penalties)
3. Confidence Calibration Framework (Expected Calibration Error - ECE, Brier Score)

Spec: evaluation_framework.md §2 & §3.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

# Severity Cost Matrix (evaluation_framework.md §2.2 & Hackerrank canonical actions: notify, digest, mute)
SEVERITY_COST_MATRIX: dict[tuple[str, str], int] = {
    # True Class -> Predicted Class : Penalty Points
    ("notify", "notify"): 0,
    ("notify", "digest"): 8,   # HIGH FAIL: Urgent missed or delayed
    ("notify", "mute"): 15,    # FATAL FAIL: Urgent muted

    ("digest", "notify"): 2,   # Minor Annoyance: Low priority interrupted user
    ("digest", "digest"): 0,
    ("digest", "mute"): 3,     # Moderate: Digest items muted

    ("mute", "notify"): 5,     # High Annoyance: Spam/mute interrupted user
    ("mute", "digest"): 1,     # Negligible: Spam in digest
    ("mute", "mute"): 0,
}

# Legacy mapping for backwards compatibility with test inputs
_ACTION_NORMALIZATION: dict[str, str] = {
    "NOTIFY_IMMEDIATELY": "notify",
    "DELIVER_IMMEDIATELY": "notify",
    "TRIGGER_EMERGENCY_OVERRIDE": "notify",
    "DELIVER_SILENTLY": "digest",
    "DELIVER_SILENT": "digest",
    "SUMMARIZE_IN_BATCH": "digest",
    "SUMMARIZE_LATER": "digest",
    "BATCH_DIGEST": "digest",
    "DO_NOT_DISTURB": "mute",
    "SUPPRESS_SPAM": "mute",
    "SUPPRESS_MUTE": "mute",
    "NOTIFY": "notify",
    "DIGEST": "digest",
    "MUTE": "mute",
}

VALID_ACTIONS = ["notify", "digest", "mute"]


def normalize_action(act: str) -> str:
    """Normalize action string to canonical lower-case NotificationAction ('notify', 'digest', 'mute')."""
    cleaned = str(act).strip()
    if cleaned in _ACTION_NORMALIZATION:
        return _ACTION_NORMALIZATION[cleaned]
    return cleaned.lower()



@dataclass
class EvaluationMetricsResult:
    """Holds comprehensive quantitative evaluation results."""

    accuracy: float
    macro_f1: float
    precision_per_action: dict[str, float]
    recall_per_action: dict[str, float]
    f1_per_action: dict[str, float]
    total_penalty_score: int
    penalty_per_1000: float
    ece_score: float
    brier_score: float
    passed_gates: bool
    gate_failures: list[str] = field(default_factory=list)


class MetricsEngine:
    """Quantitative evaluation calculator."""

    def __init__(self) -> None:
        """Initialize MetricsEngine."""
        pass

    def compute_all_metrics(
        self,
        y_true: Sequence[str],
        y_pred: Sequence[str],
        confidences: Sequence[float],
    ) -> EvaluationMetricsResult:
        """Compute complete metric suite on predictions.

        Args:
            y_true: Ground truth action labels.
            y_pred: Model predicted action labels.
            confidences: Model output confidence scores (0.0-1.0).

        Returns:
            EvaluationMetricsResult with all metrics.
        """
        n = len(y_true)
        if n == 0:
            raise ValueError("Cannot evaluate empty dataset")

        norm_true = [normalize_action(t) for t in y_true]
        norm_pred = [normalize_action(p) for p in y_pred]

        # 1. Classification Metrics
        correct = sum(1 for t, p in zip(norm_true, norm_pred, strict=False) if t == p)
        accuracy = correct / n

        precision_map: dict[str, float] = {}
        recall_map: dict[str, float] = {}
        f1_map: dict[str, float] = {}

        for action in VALID_ACTIONS:
            tp = sum(1 for t, p in zip(norm_true, norm_pred, strict=False) if t == action and p == action)
            fp = sum(1 for t, p in zip(norm_true, norm_pred, strict=False) if t != action and p == action)
            fn = sum(1 for t, p in zip(norm_true, norm_pred, strict=False) if t == action and p != action)

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            precision_map[action] = round(prec, 4)
            recall_map[action] = round(rec, 4)
            f1_map[action] = round(f1, 4)

        macro_f1 = sum(f1_map.values()) / len(VALID_ACTIONS)

        # 2. Risk-Weighted Penalty Matrix
        total_penalty = 0
        for t, p in zip(norm_true, norm_pred, strict=False):
            penalty = SEVERITY_COST_MATRIX.get((t, p), 5)  # default penalty 5 for unknown
            total_penalty += penalty


        penalty_per_1000 = (total_penalty / n) * 1000.0

        # 3. Expected Calibration Error (ECE) & Brier Score
        ece_score = self.compute_ece(y_true, y_pred, confidences)
        brier_score = self.compute_brier_score(y_true, y_pred, confidences)

        # CI/CD Gate Verification (evaluation_framework.md §7)
        gate_failures = []
        if macro_f1 < 0.92:
            gate_failures.append(f"Macro F1 ({macro_f1:.3f}) < target 0.92")
        if penalty_per_1000 >= 50.0:
            gate_failures.append(f"Risk Penalty ({penalty_per_1000:.1f}/1000) >= target 50.0")
        if ece_score > 0.05:
            gate_failures.append(f"ECE Score ({ece_score:.3f}) > target 0.05")

        passed_gates = len(gate_failures) == 0

        return EvaluationMetricsResult(
            accuracy=round(accuracy, 4),
            macro_f1=round(macro_f1, 4),
            precision_per_action=precision_map,
            recall_per_action=recall_map,
            f1_per_action=f1_map,
            total_penalty_score=total_penalty,
            penalty_per_1000=round(penalty_per_1000, 2),
            ece_score=round(ece_score, 4),
            brier_score=round(brier_score, 4),
            passed_gates=passed_gates,
            gate_failures=gate_failures,
        )

    def compute_ece(
        self,
        y_true: Sequence[str],
        y_pred: Sequence[str],
        confidences: Sequence[float],
        num_bins: int = 10,
    ) -> float:
        """Compute Expected Calibration Error (ECE).

        Formula: ECE = sum(|B_m|/N * |acc(B_m) - conf(B_m)|)
        """
        n = len(y_true)
        if n == 0:
            return 0.0

        bins: list[list[tuple[bool, float]]] = [[] for _ in range(num_bins)]

        for t, p, c in zip(y_true, y_pred, confidences, strict=False):
            is_correct = (t == p)
            bin_idx = min(int(c * num_bins), num_bins - 1)
            bins[bin_idx].append((is_correct, c))

        ece = 0.0
        for b in bins:
            if not b:
                continue
            bin_size = len(b)
            avg_acc = sum(1 for is_corr, _ in b if is_corr) / bin_size
            avg_conf = sum(conf for _, conf in b) / bin_size
            ece += (bin_size / n) * abs(avg_acc - avg_conf)

        return ece

    def compute_brier_score(
        self,
        y_true: Sequence[str],
        y_pred: Sequence[str],
        confidences: Sequence[float],
    ) -> float:
        """Compute Brier Score for confidence calibration.

        Brier = mean((conf - binary_outcome)^2)
        """
        n = len(y_true)
        if n == 0:
            return 0.0

        squared_errors = [
            (c - (1.0 if t == p else 0.0)) ** 2
            for t, p, c in zip(y_true, y_pred, confidences, strict=False)
        ]
        return sum(squared_errors) / n
