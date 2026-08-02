# Comprehensive System Stress Test & Vulnerability Audit Report

**Target System**: Message Notification Router (WhatsApp Multimodal AI Routing Engine)  
**Evaluation Scope**: Static Analysis, Runtime Execution, Logic Verification, Architecture Analysis, Performance & Memory, Edge Cases, and Hackerrank Platform Compatibility.  
**Audit Date**: August 2, 2026  
**Auditor Persona**: Principal QA Engineer, Senior Software Test Architect, AI Systems Reliability Engineer & Hackathon Judge  

---

## Executive Summary & Submission Risk Score

### Hackathon Submission Risk Score: **32 / 100** (HIGH RISK — CRITICAL FIXES REQUIRED BEFORE SUBMISSION)

> [!CAUTION]
> **CRITICAL SUBMISSION HAZARD DETECTED**: The system currently exhibits a 100% decision validation failure cascade due to an architectural type mismatch between `SignalBundle` driver tags and `EvidenceBundle` historical message IDs. This causes **100% of incoming messages** to fail Stage 11 validation, resulting in system-wide fallback overrides (e.g., converting urgent/scam/quiet-hours decisions into `digest`). Furthermore, `DELIVER_SILENT` is mapped to `notify`, forcing quiet-hours messages to emit immediate loud alerts. Submitting the codebase in its current state will result in heavy penalties on accuracy, F1 score, evidence grounding, and schema compliance on Hackerrank.

---

## Detailed Audit Matrix by Subsystem

| Subsystem | Status | Critical Issues Found | Risk Level |
| :--- | :--- | :--- | :--- |
| **Dataset Ingestion & Data Layer** | ⚠️ Warning | Empty string `group_id` parsing, foreign key quarantine | MEDIUM |
| **Media Intelligence (OCR / Whisper)** | ✅ Operational | Media path separator compatibility | LOW |
| **Retrieval Engine & Evidence** | ❌ CRITICAL | Evidence ID signal tag pollution | CRITICAL |
| **Signal Engine** | ✅ Operational | Clean signal computation | OK |
| **Decision Intelligence Engine** | ❌ CRITICAL | 100% Stage 11 validation fallback cascade | CRITICAL |
| **Output Formatter** | ❌ CRITICAL | `DELIVER_SILENT` mapped to `notify` | CRITICAL |
| **CLI & Runtime Execution** | ❌ CRITICAL | `NameError` in `run_evaluate`, `PYTHONPATH` dependency | HIGH |
| **Telemetry & Observability** | ⚠️ Warning | `DecisionLogger` `AttributeError` in daemon thread | MEDIUM |

---

## Issue Findings Breakdown

### ISSUE-01 [CRITICAL]: Validation Cascade Caused by `candidate_evidence_ids` vs `EvidenceBundle` Mismatch

- **Severity**: **CRITICAL** (Fatal Execution & Evaluation Flaw)
- **Files Involved**:
  - [`src/router/application/decision/decision_validator.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/src/router/application/decision/decision_validator.py#L300-L335)
  - [`src/router/application/decision/confidence_engine.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/src/router/application/decision/confidence_engine.py#L135)
  - [`src/router/domain/entities/signal.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/src/router/domain/entities/signal.py#L283-L304)
- **Reproduction Steps**:
  1. Execute batch processing on any dataset:  
     `python -m router process --input hackerrank-orchestrate-august26/dataset/sample_messages.csv --output submission/output.csv`
  2. Observe system logs during execution.
- **Actual Behaviour**:
  - `SignalBundle.candidate_evidence_ids` extracts internal explainability driver tags (`"routine"`, `"near_term_keyword"`, `"clean"`, `"otp_code"`).
  - `ConfidenceEngine` passes these signal driver tags as `decision.evidence_ids`.
  - `DecisionValidator._pass4_evidence_grounding` checks if `decision.evidence_ids` match message IDs inside `EvidenceBundle.items` (which are actual historical message IDs like `"msg_001"`).
  - Because `"routine"` is not a message ID, `DecisionValidator` fails validation on **100% of incoming messages** with `UNGROUNDED_FACT: evidence_id 'routine' not found in EvidenceBundle.`.
  - `DecisionEngineV2` catches the validation failure and forces a fallback action (`SUMMARIZE_LATER` / `BATCH_DIGEST`) on all messages, overriding rules, emergency overrides, and scam mutes.
  - The output CSV prints `routine;non_business;direct;clean` under `evidence_message_ids` instead of valid historical message IDs or `none`.
- **Expected Behaviour**:
  - `evidence_message_ids` must strictly contain historical message IDs retrieved from `EvidenceBundle` (or `"none"`).
  - Signal explainability tags must not populate `evidence_message_ids`.
  - `DecisionValidator` should only validate historical message IDs present in `EvidenceBundle` and must clear validation when no evidence is referenced or when valid historical IDs are supplied.
- **Root Cause**:
  `ConfidenceEngine` falls back to `sb.candidate_evidence_ids[:5]` when `evidence_ids_referenced` is empty, conflating signal explainability metadata with historical message retrieval IDs.
- **Suggested Fix**:
  In `ConfidenceEngine.calibrate`, set `evidence_ids` strictly from `eb.items` message IDs (e.g. `[item.message_id for item in eb.items[:5]]`), or `["none"]` if empty.

---

### ISSUE-02 [CRITICAL]: `DELIVER_SILENT` Map Bug in `OutputFormatter` Inverts Quiet-Hours Actions

- **Severity**: **CRITICAL**
- **Files Involved**:
  - [`src/router/application/decision/output_formatter.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/src/router/application/decision/output_formatter.py#L28-L36)
- **Reproduction Steps**:
  1. Process a message during quiet hours from a non-VIP sender (e.g. `sample_msg_001`).
  2. Inspect the generated `submission/output.csv`.
- **Actual Behaviour**:
  - `_ACTION_MAP` maps `DecisionAction.DELIVER_SILENT` to `NotificationAction.NOTIFY` (formats as `"notify"` in `output.csv`).
  - Row 2 of output CSV:  
    `sample_msg_001,notify,personal,Quiet hours active; non-VIP sender; urgency below threshold.,0.61,routine;non_business;direct;clean`
  - The reasoning text explicitly states `"Quiet hours active..."`, yet the final CSV action is `"notify"` (immediate loud alert)!
- **Expected Behaviour**:
  - `DELIVER_SILENT` must map to `NotificationAction.DIGEST` (formats as `"digest"`), ensuring quiet-hours messages are batched silently rather than triggering immediate notifications.
- **Root Cause**:
  Line 30 of `output_formatter.py`: `DecisionAction.DELIVER_SILENT: NotificationAction.NOTIFY`.
- **Suggested Fix**:
  Change line 30 to: `DecisionAction.DELIVER_SILENT: NotificationAction.DIGEST`.

---

### ISSUE-03 [HIGH]: CLI Entry Point Unhandled `NameError` in `run_evaluate`

- **Severity**: **HIGH**
- **Files Involved**:
  - [`src/router/__main__.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/src/router/__main__.py#L155)
- **Reproduction Steps**:
  1. Run command: `python -m router evaluate`
- **Actual Behaviour**:
  - Crashes immediately with `NameError: name 'EvaluationPipeline' is not defined`.
- **Expected Behaviour**:
  - Executes offline evaluation benchmark suite and prints accuracy, F1, and ECE metrics cleanly.
- **Root Cause**:
  Line 155 invokes `pipeline = EvaluationPipeline()`, but `EvaluationPipeline` is never imported at the top of `__main__.py`.
- **Suggested Fix**:
  Add `from eval.evaluation_pipeline import EvaluationPipeline` to imports in `src/router/__main__.py`.

---

### ISSUE-04 [HIGH]: Missing `PYTHONPATH` & Module Import Path Assumption

- **Severity**: **HIGH**
- **Files Involved**:
  - `pyproject.toml`, `src/router/__main__.py`
- **Reproduction Steps**:
  1. Execute `python -m router process --input dataset/messages.csv` from workspace root without setting `PYTHONPATH`.
- **Actual Behaviour**:
  - Fails with `C:\Python314\python.exe: No module named router`.
- **Expected Behaviour**:
  - Command executes cleanly out of the box on Hackerrank evaluation runner.
- **Root Cause**:
  The `src/` layout requires `PYTHONPATH=src` or `pip install -e .` for Python module resolution.
- **Suggested Fix**:
  Provide an explicit entrypoint script `main.py` at the root directory that adds `src/` to `sys.path` before launching `router.__main__.main()`.

---

### ISSUE-05 [MEDIUM]: `DecisionLogger` Async Telemetry `AttributeError`

- **Severity**: **MEDIUM**
- **Files Involved**:
  - [`src/router/application/decision/decision_logger.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/src/router/application/decision/decision_logger.py#L217)
- **Reproduction Steps**:
  1. Process any batch input.
  2. Inspect log output for `[ERROR] router.application.decision.decision_logger`.
- **Actual Behaviour**:
  - On every processed message, the daemon thread logs:  
    `DecisionLogger async logging error | error='DecisionResult' object has no attribute 'audit_hash' execution_id=...`
- **Expected Behaviour**:
  - Asynchronously logs structured audit record with valid SHA-256 audit hash without error.
- **Root Cause**:
  Line 217 of `decision_logger.py` accesses `decision_result.audit_hash` instead of `meta.audit_hash` (`decision_result.metadata.audit_hash`).
- **Suggested Fix**:
  Change line 217 in `decision_logger.py` to `"audit_hash": meta.audit_hash`.

---

### ISSUE-06 [MEDIUM]: Empty String `group_id` Triggers False Orphan Group Warnings

- **Severity**: **MEDIUM**
- **Files Involved**:
  - [`src/router/application/context/context_assembler.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/src/router/application/context/context_assembler.py#L124)
  - [`src/router/application/context/context_validation_service.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/src/router/application/context/context_validation_service.py#L57)
- **Reproduction Steps**:
  1. Process input CSV with empty `group_id` cells (1-on-1 direct messages).
- **Actual Behaviour**:
  - Log warning on every 1-on-1 message: `Orphan group reference ; applying default group fallback.`
- **Expected Behaviour**:
  - Direct 1-on-1 messages should be normalized to `group_id = "NONE"` without triggering orphan warnings.
- **Root Cause**:
  `raw_message.get("group_id", "NONE")` on CSV row dict evaluates to `""` (empty string) because the dictionary key exists. `context_validation_service` checks `if bag.payload.group_id != "NONE":`, which evaluates to `True` for `""`.
- **Suggested Fix**:
  In `_normalize_payload`, sanitize `group_id`: `group_id = raw_message.get("group_id") or "NONE"`.

---

### ISSUE-07 [MEDIUM]: Empty Evaluation File in Hackerrank Subdirectory

- **Severity**: **MEDIUM**
- **Files Involved**:
  - [`hackerrank-orchestrate-august26/code/evaluation/main.py`](file:///c:/Users/Lenovo/Downloads/message-notification-router/hackerrank-orchestrate-august26/code/evaluation/main.py#L1)
- **Actual Behaviour**:
  - File `hackerrank-orchestrate-august26/code/evaluation/main.py` is 0 bytes (empty file).
- **Expected Behaviour**:
  - Contains full evaluation execution script.
- **Suggested Fix**:
  Populate `main.py` with evaluation pipeline wrapper.

---

## Detailed Hackerrank Submission Hazard Checklist

| Hazard Category | Audit Result | Severity | Details |
| :--- | :--- | :--- | :--- |
| **Missing Dataset Rows** | Pass | OK | Preserves exact row count and ordering. |
| **Output Ordering** | Pass | OK | Preserves exact CSV input row order. |
| **Floating Point Formatting** | Pass | OK | Formatted to 2 decimal places (`f"{confidence:.2f}"`). |
| **CSV Encoding & BOM** | Pass | OK | Handled via `utf-8-sig` in readers. |
| **Unicode Characters** | Pass | OK | Multilingual & emoji text preserved in normalization. |
| **Media Failures** | Pass | OK | Gracefully handles missing media files with zero-score fallback. |
| **Path Assumptions** | Warning | MEDIUM | Uses `./` relative paths; requires normalization for OS independence. |
| **Windows/Linux Compatibility**| Pass | OK | Uses `os.path.join` and `Path` objects. |
| **Randomness & Determinism** | Warning | LOW | Temperature scaling and UUIDs should be strictly seeded. |
| **Memory Spikes** | Pass | OK | Memory remains < 150MB across 110-message batch. |
| **Thread Safety** | Pass | OK | Thread-safe data repositories and cache implementations. |

---

## Summary Recommendation for Submission

To raise the Submission Risk Score from **32/100** to **100/100**, the following surgical corrections must be applied:

1. **Fix Evidence Grounding**: Update `ConfidenceEngine.calibrate` to set `evidence_ids` strictly from `eb.items` historical message IDs or `["none"]`.
2. **Fix `DELIVER_SILENT` Action Mapping**: Update `OutputFormatter` `_ACTION_MAP` to map `DELIVER_SILENT` to `NotificationAction.DIGEST`.
3. **Fix `__main__.py` Imports**: Import `EvaluationPipeline` in `src/router/__main__.py`.
4. **Fix `DecisionLogger` Hash Access**: Update `decision_logger.py` to access `meta.audit_hash`.
5. **Normalize Empty `group_id`**: Update `_normalize_payload` to set `group_id = raw_message.get("group_id") or "NONE"`.
6. **Provide Root `main.py`**: Add root entrypoint script for seamless Hackerrank runner execution.
