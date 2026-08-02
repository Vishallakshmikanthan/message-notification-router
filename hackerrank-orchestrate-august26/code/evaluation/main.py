"""Evaluation entrypoint runner for Hackerrank benchmark platform."""

import os
import sys
from pathlib import Path

# Add project root and src directory to sys.path
code_dir = Path(__file__).resolve().parent.parent
repo_root = code_dir.parent.parent
src_dir = repo_root / "src"

for path in (str(src_dir), str(repo_root)):
    if path not in sys.path:
        sys.path.insert(0, path)

from eval.evaluation_pipeline import EvaluationPipeline


def main() -> None:
    """Run evaluation benchmark pipeline on dataset."""
    pipeline = EvaluationPipeline()
    dataset_path = os.environ.get("DATASET_PATH", "hackerrank-orchestrate-august26/dataset/sample_messages.csv")
    report_file = os.environ.get("REPORT_FILE", "reports/eval_results/eval_report.json")
    
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    res = pipeline.run_evaluation(dataset_path, report_file)
    print("\n================ EVALUATION SUMMARY ================")
    print(f"Accuracy:        {res.accuracy:.4f}")
    print(f"Macro F1:        {res.macro_f1:.4f}")
    print(f"Risk Penalty:    {res.penalty_per_1000:.2f} / 1000 items")
    print(f"ECE Score:       {res.ece_score:.4f}")
    print(f"Passed Gates:    {res.passed_gates}")
    if res.gate_failures:
        print(f"Gate Failures:   {res.gate_failures}")
    print("===================================================\n")


if __name__ == "__main__":
    main()
