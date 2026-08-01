"""Eval Package Init.

Exports evaluation framework and submission tools:
- MetricsEngine: Macro F1, ECE, Brier, penalty matrix.
- EvaluationPipeline: Harness for benchmark datasets.
- RegressionTester: CI/CD gate validator.
- PromptEvaluator: LLM-as-a-Judge rubrics.
- OutputCSVValidator: CSV schema validator.
- PerformanceMetricsTracker: Latency & token SLA analyzer.
- SubmissionValidator: Final package QA checker.
"""

from eval.evaluation_pipeline import EvaluationPipeline
from eval.metrics_engine import EvaluationMetricsResult, MetricsEngine
from eval.output_validator import OutputCSVValidator
from eval.performance_metrics import PerformanceMetricsTracker, PerformanceReport
from eval.prompt_evaluator import PromptEvaluator, PromptJudgeScore
from eval.regression_tester import RegressionTester
from eval.submission_validator import SubmissionValidator

__all__ = [
    "MetricsEngine",
    "EvaluationMetricsResult",
    "EvaluationPipeline",
    "RegressionTester",
    "PromptEvaluator",
    "PromptJudgeScore",
    "OutputCSVValidator",
    "PerformanceMetricsTracker",
    "PerformanceReport",
    "SubmissionValidator",
]
