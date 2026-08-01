"""Evaluation Pipeline — Offline evaluation runner across benchmark datasets.

Executes benchmark suites across test datasets specified in evaluation_framework.md §5:
- Golden Master Dataset (1,500 items)
- Adversarial & Edge-Case Dataset (500 items)
- Multimodal Noise Dataset (300 items)
- Synthetic Distribution Shift Dataset (500 items)

Spec: evaluation_framework.md §5.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from eval.metrics_engine import EvaluationMetricsResult, MetricsEngine
from router.application.decision.decision_engine import DecisionEngineV2
from router.domain.entities.context import MessageContext

logger = logging.getLogger(__name__)


class EvaluationPipeline:
    """Offline Evaluation Pipeline Harness."""

    def __init__(self, decision_engine: Optional[DecisionEngineV2] = None) -> None:
        """Initialize evaluation pipeline."""
        self.decision_engine = decision_engine or DecisionEngineV2()
        self.metrics_engine = MetricsEngine()
        logger.info("EvaluationPipeline initialized")

    def run_evaluation(
        self,
        dataset_path: str,
        output_report_path: Optional[str] = None,
    ) -> EvaluationMetricsResult:
        """Run evaluation on dataset JSON/CSV file.

        Args:
            dataset_path: Path to benchmark dataset JSON file.
            output_report_path: Optional destination path for eval report.

        Returns:
            EvaluationMetricsResult object.
        """
        logger.info("Starting evaluation pipeline run", extra={"dataset": dataset_path})
        start_time = time.perf_counter()

        data_items = self._load_dataset(dataset_path)
        y_true: List[str] = []
        y_pred: List[str] = []
        confidences: List[float] = []
        results_list: List[Dict[str, Any]] = []

        for item in data_items:
            true_action = item.get("ground_truth_action", item.get("expected_action", "DELIVER_SILENTLY"))
            context = self._build_mock_context(item)

            try:
                action_enum, _, reason, confidence, evidence = self.decision_engine.evaluate_routing(context)
                pred_action = action_enum.name if hasattr(action_enum, "name") else str(action_enum)
            except Exception as exc:
                logger.error("Error evaluating item", extra={"item_id": item.get("message_id"), "error": str(exc)})
                pred_action = "DELIVER_SILENTLY"
                confidence = 0.40
                reason = f"Error: {exc}"
                evidence = []

            y_true.append(true_action)
            y_pred.append(pred_action)
            confidences.append(confidence)

            results_list.append({
                "message_id": item.get("message_id", "UNKNOWN"),
                "true_action": true_action,
                "pred_action": pred_action,
                "confidence": confidence,
                "reason": reason,
                "is_correct": true_action == pred_action,
            })

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        metrics = self.metrics_engine.compute_all_metrics(y_true, y_pred, confidences)

        logger.info(
            "Evaluation pipeline completed",
            extra={
                "items_count": len(data_items),
                "duration_ms": round(duration_ms, 2),
                "macro_f1": metrics.macro_f1,
                "penalty_score": metrics.penalty_per_1000,
                "passed_gates": metrics.passed_gates,
            },
        )

        if output_report_path:
            self._save_report(output_report_path, metrics, results_list, duration_ms)

        return metrics

    def _load_dataset(self, path: str) -> List[Dict[str, Any]]:
        """Load benchmark dataset file."""
        p = Path(path)
        if not p.exists():
            logger.warning(f"Dataset path {path} not found. Generating synthetic mock evaluation items.")
            return self._generate_synthetic_benchmark_items(100)

        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("items", [])

    @staticmethod
    def _build_mock_context(item: Dict[str, Any]) -> MessageContext:
        """Construct MessageContext from dataset item."""
        from router.domain.entities.message import Message

        msg_text = item.get("text", item.get("message_text", "Sample message text"))
        msg_id = item.get("message_id", "msg_test_001")
        user_id = item.get("user_id", "user_123")

        from router.domain.value_objects.message_type import MessageType

        core_msg = Message(
            message_id=msg_id,
            user_id=user_id,
            conversation_type="personal",
            message_text=msg_text,
            sender_id=item.get("sender_id", "sender_456"),
        )
        object.__setattr__(core_msg, "cleaned_text", msg_text)
        object.__setattr__(core_msg, "raw_text_content", msg_text)
        object.__setattr__(core_msg, "contains_links", False)
        object.__setattr__(core_msg, "is_forwarded", False)
        object.__setattr__(core_msg, "is_frequently_forwarded", False)
        object.__setattr__(core_msg, "message_type", "text")
        object.__setattr__(core_msg, "forward_count", 0)
        object.__setattr__(core_msg, "char_count", len(msg_text))

        return MessageContext(
            message_id=msg_id,
            user_id=user_id,
            core_message=core_msg,
        )

    @staticmethod
    def _generate_synthetic_benchmark_items(count: int = 100) -> List[Dict[str, Any]]:
        """Generate synthetic dataset items for test runs."""
        actions = ["NOTIFY_IMMEDIATELY", "DELIVER_SILENTLY", "SUMMARIZE_IN_BATCH", "DO_NOT_DISTURB"]
        items = []
        for i in range(count):
            act = actions[i % len(actions)]
            items.append({
                "message_id": f"synthetic_msg_{i+1:03d}",
                "text": f"Synthetic test message text {i+1} for action {act}",
                "expected_action": act,
                "ground_truth_action": act,
                "sender_id": f"sender_{i % 10}",
                "user_id": "user_main",
            })
        return items

    @staticmethod
    def _save_report(
        path: str,
        metrics: EvaluationMetricsResult,
        results_list: List[Dict[str, Any]],
        duration_ms: float,
    ) -> None:
        """Save evaluation report JSON artifact."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        report_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_ms": round(duration_ms, 2),
            "summary": {
                "accuracy": metrics.accuracy,
                "macro_f1": metrics.macro_f1,
                "total_penalty_score": metrics.total_penalty_score,
                "penalty_per_1000": metrics.penalty_per_1000,
                "ece_score": metrics.ece_score,
                "brier_score": metrics.brier_score,
                "passed_gates": metrics.passed_gates,
                "gate_failures": metrics.gate_failures,
            },
            "per_action_metrics": {
                "precision": metrics.precision_per_action,
                "recall": metrics.recall_per_action,
                "f1": metrics.f1_per_action,
            },
            "item_results_sample": results_list[:20],
        }

        with p.open("w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        logger.info(f"Saved evaluation report artifact to {path}")
