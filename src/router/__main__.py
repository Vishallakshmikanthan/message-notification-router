"""CLI Entry Point & Batch Execution Runner for Notification Router.

Implements CLI Workflow Interface from deployment.md §6:
- process: Batch processing mode for input messages CSV/JSON -> output.csv
- evaluate: Offline evaluation & benchmark suite mode -> reports/
- serve: REST API service runner
- healthcheck: System diagnostic check

Spec: deployment.md §6.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path

# Ensure 'src' and project root directory are in sys.path for resolution
root_dir = Path(__file__).resolve().parent.parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from eval.evaluation_pipeline import EvaluationPipeline
from eval.output_validator import OutputCSVValidator
from router.application.context.context_assembler import ContextAssembler
from router.application.data.data_manager import DataManager
from router.application.decision.decision_engine import DecisionEngineV2

from router.core.config.settings import get_settings
from router.core.logging.logger import configure_logger, get_logger
from router.domain.entities.context import MessageContext
from router.infrastructure.repositories.context_repository_registry import (
    ContextRepositoryRegistry,
)

settings = get_settings()
configure_logger(log_level=settings.log_level)
logger = get_logger("router.cli")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="python -m router",
        description="WhatsApp Message Notification Router CLI",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command 1: process (batch runner)
    proc_parser = subparsers.add_parser("process", help="Process input messages batch")
    proc_parser.add_argument("--input", required=True, help="Input CSV/JSON path")
    proc_parser.add_argument("--output", default="submission/output.csv", help="Output CSV path")
    proc_parser.add_argument("--tier", default="auto", help="Execution tier mode")
    proc_parser.add_argument("--workers", type=int, default=4, help="Worker concurrency")

    # Command 2: evaluate (benchmark runner)
    eval_parser = subparsers.add_parser("evaluate", help="Run offline evaluation benchmark suite")
    eval_parser.add_argument("--dataset", default="data/golden_master.json", help="Dataset path")
    eval_parser.add_argument("--report-dir", default="reports/eval_results", help="Report destination dir")

    # Command 3: serve (REST API)
    serve_parser = subparsers.add_parser("serve", help="Run REST API production service")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host IP")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port number")
    serve_parser.add_argument("--workers", type=int, default=4, help="Worker process count")

    # Command 4: healthcheck
    subparsers.add_parser("healthcheck", help="Run system diagnostics")

    args = parser.parse_args()

    if args.command == "process":
        run_process(args.input, args.output)
    elif args.command == "evaluate":
        run_evaluate(args.dataset, args.report_dir)
    elif args.command == "serve":
        run_serve(args.host, args.port, args.workers)
    elif args.command == "healthcheck":
        run_healthcheck()
    else:
        parser.print_help()
        sys.exit(1)


def run_process(input_path: str, output_path: str) -> None:
    """Process batch input file and generate output.csv using full architecture pipeline."""
    logger.info(f"Processing input batch from {input_path} -> {output_path}")
    in_p = Path(input_path)
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    dataset_dir = in_p.parent if in_p.is_file() else in_p
    logger.info(f"Initializing DataManager data layer with dataset_dir={dataset_dir}")
    data_manager = DataManager(dataset_dir=str(dataset_dir))
    data_manager.initialize()

    registry = ContextRepositoryRegistry(
        messages_repo=data_manager.message_repo,
        users_repo=data_manager.user_repo,
        groups_repo=data_manager.group_repo,
        business_accounts_repo=data_manager.business_repo,
        message_history_repo=data_manager.history_repo,
        message_events_repo=data_manager.event_repo,
        daily_notification_summary_repo=data_manager.summary_repo,
    )
    context_assembler = ContextAssembler(registry=registry)
    engine = DecisionEngineV2()

    items = []
    if in_p.suffix.lower() == ".csv":
        with in_p.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            items = list(reader)
    else:
        with in_p.open("r", encoding="utf-8") as f:
            data = json.load(f)
            items = data if isinstance(data, list) else data.get("items", [])

    results = []
    for item in items:
        context = context_assembler.assemble(item)
        action_enum, msg_type_enum, reason, confidence, evidence_list = engine.evaluate_routing(context)

        action_str = action_enum.value if hasattr(action_enum, "value") else str(action_enum).lower()
        msg_type_str = msg_type_enum.value if hasattr(msg_type_enum, "value") else str(msg_type_enum).lower()

        valid_ev = [str(e).strip() for e in evidence_list if e and str(e).strip().lower() != "none"]
        evidence_str = ";".join(valid_ev) if valid_ev else "none"

        results.append({
            "message_id": context.message_id or item.get("message_id", "UNKNOWN"),
            "action": action_str,
            "message_type": msg_type_str,
            "reason": reason,
            "confidence": f"{confidence:.2f}",
            "evidence_message_ids": evidence_str,
        })

    fieldnames = ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]
    with out_p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"Output saved to {output_path}. Running Hackerrank schema validation...")
    validator = OutputCSVValidator()
    val_res = validator.validate_file(output_path)
    if val_res["is_valid"]:
        logger.info("output.csv validation PASSED successfully!")
    else:
        logger.error(f"output.csv validation FAILED: {val_res['errors']}")



def run_evaluate(dataset_path: str, report_dir: str) -> None:
    """Run offline evaluation pipeline."""
    pipeline = EvaluationPipeline()
    report_file = Path(report_dir) / "eval_report.json"
    res = pipeline.run_evaluation(dataset_path, str(report_file))
    print("\n================ EVALUATION SUMMARY ================")
    print(f"Accuracy:        {res.accuracy:.4f}")
    print(f"Macro F1:        {res.macro_f1:.4f}")
    print(f"Risk Penalty:    {res.penalty_per_1000:.2f} / 1000 items")
    print(f"ECE Score:       {res.ece_score:.4f}")
    print(f"Passed Gates:    {res.passed_gates}")
    if res.gate_failures:
        print(f"Gate Failures:   {res.gate_failures}")
    print("===================================================\n")


def run_serve(host: str, port: int, workers: int) -> None:
    """Run Uvicorn FastAPI server."""
    import uvicorn
    uvicorn.run("router.main:app", host=host, port=port, workers=workers)


def run_healthcheck() -> None:
    """Run healthcheck diagnostics."""
    logger.info("Running healthcheck diagnostics...")
    try:
        engine = DecisionEngineV2()
        logger.info("DecisionEngineV2 initialized successfully: OK")
        print("SYSTEM HEALTH: OK")
    except Exception as exc:
        logger.error(f"Healthcheck failed: {exc}")
        print("SYSTEM HEALTH: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
