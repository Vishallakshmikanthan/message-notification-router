# End-to-End Decision Flow & Execution Pipeline

## 1. Overview of the 12-Stage Decision Pipeline

The decision process is structured into 12 discrete, deterministic, and traceable stages. Every incoming WhatsApp notification context payload passes through this pipeline to yield a calibrated, verified routing decision.

```
+---------------------------------------------------------------------------------------------------+
|                                 12-STAGE DECISION PIPELINE FLOW                                   |
|                                                                                                   |
|  [Stage 1: MessageContext Ingestion]                                                              |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 2: SignalBundle Assembly]                                                                 |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 3: EvidenceBundle Assembly]                                                               |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 4: Decision Preprocessing] ─── (Sanitize, Normalize, Filter)                              |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 5: Rule Engine Evaluation] ─── Fired? ───► YES ───► [FAST-PATH: Jump to Stage 9]          |
|        │                                                                                          |
|        │ NO                                                                                       |
|        v                                                                                          |
|  [Stage 6: Decision Orchestrator Context Construction]                                            |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 7: LLM Reasoner Execution] ─── Timeout/Err? ─► YES ──► [FALLBACK-PATH: Jump to Stage 11]  |
|        │                                                                                          |
|        │ Success                                                                                  |
|        v                                                                                          |
|  [Stage 8: Decision Verification] ─── Logical Contradiction? ─► YES ─► Apply Local Correction    |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 9: Confidence Calibration] ─── Adjust for signal agreement/disagreement                   |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 10: Evidence Verification] ─── Grounding check against EvidenceBundle                    |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 11: Output Validator] ──────── Check Schema & Ranges ─► Invalid? ─► Inject Fallback      |
|        │                                                                                          |
|        v                                                                                          |
|  [Stage 12: Final Decision Delivery & Async Audit Logging]                                        |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Comprehensive 12-Stage Pipeline Specifications

### Stage 1: `MessageContext` Ingestion
* **Input**: Inbound WhatsApp notification payload event.
* **Operation**: Parse raw message fields into `MessageContext` struct (message ID, sender ID, chat type, timestamp, text payload, media metadata flags).
* **Output**: Immutable `MessageContext` object.

### Stage 2: `SignalBundle` Assembly
* **Input**: `MessageContext` + feature store references.
* **Operation**: Retrieve calculated numeric and categorical signals (urgency score, sentiment score, spam score, relationship closeness, quiet hours flag).
* **Output**: `SignalBundle` object.

### Stage 3: `EvidenceBundle` Assembly
* **Input**: `MessageContext` + `SignalBundle`.
* **Operation**: Fetch relevant historical facts, calendar commitments, and message context snippets via hybrid retrieval.
* **Output**: `EvidenceBundle` object containing top-5 grounded snippets with relevance scores.

### Stage 4: `Decision Preprocessing`
* **Input**: `MessageContext`, `SignalBundle`, `EvidenceBundle`.
* **Operation**:
  * Normalize timestamps into target user's local timezone.
  * Sanitize text (strip control characters, detect corrupt unicode).
  * Validate structural integrity of input bundles.
* **Output**: Cleaned, unified `DecisionContext` struct ready for engine consumption.

### Stage 5: `Rule Engine Evaluation` (Branching Point)
* **Input**: `DecisionContext`.
* **Operation**: Execute deterministic rule set sequentially (Level 0 and Level 1).
* **Branching Logic**:
  * If a rule matches (`rule_fired == True` and `bypass_llm == True`): Bypasses Stage 6, 7, and 8; jumps directly to Stage 9 (`Confidence Calibration`).
  * If no rule matches (`rule_fired == False`): Advances to Stage 6.
* **Output**: `RuleEvaluationResult`.

### Stage 6: `Decision Orchestrator` Context Construction
* **Input**: `DecisionContext` + `RuleEvaluationResult`.
* **Operation**: Construct the prompt-free, structured context frame for the LLM Reasoner. Injects active evidence snippets, relationship scores, temporal constraints, and user activity status (`IN_MEETING`, `DRIVING`, `AVAILABLE`).
* **Output**: `ReasonerInputFrame`.

### Stage 7: `LLM Reasoner Execution`
* **Input**: `ReasonerInputFrame`.
* **Operation**: Invoke LLM `ReasoningService`. Analyze complex, multimodal, and social context features to produce recommended action, urgency/importance scores, and reasoning summary.
* **Timeout / Error Handling**: If LLM invocation times out (>250ms) or encounters API errors, trigger **Fallback Path** directly to Stage 11 with `SUMMARIZE_LATER` or `DELIVER_SILENT`.
* **Output**: `ReasoningOutput` struct.

### Stage 8: `Decision Verification`
* **Input**: `ReasoningOutput` + `DecisionContext`.
* **Operation**: Verify logic consistency of the raw LLM output.
  * Example check: If action is `DELIVER_IMMEDIATELY`, urgency score must be >= `0.60`. If contradiction found, auto-adjust action to `DELIVER_SILENT` or correct urgency score.
* **Output**: `VerifiedReasoningOutput`.

### Stage 9: `Confidence Calibration`
* **Input**: `VerifiedReasoningOutput` (or `RuleEvaluationResult` from Stage 5) + `SignalBundle`.
* **Operation**: Compute calibrated confidence:
  * Apply signal agreement/disagreement scaling matrices.
  * Apply evidence relevance adjustments.
  * Execute temperature scaling model.
* **Output**: `CalibratedDecision` containing `calibrated_confidence` (0.0 to 1.0).

### Stage 10: `Evidence Verification`
* **Input**: `CalibratedDecision` + `EvidenceBundle`.
* **Operation**: Verify factual grounding of LLM summary against `EvidenceBundle`:
  * Compute grounding index ratio.
  * If LLM summary cites facts absent from `EvidenceBundle` (potential hallucination), apply a -0.20 confidence penalty and flag `grounding_warning = True`.
* **Output**: `GroundedDecision`.

### Stage 11: `Output Validator`
* **Input**: `GroundedDecision`.
* **Operation**: Perform final multi-pass validation:
  * Validate JSON schema compliance.
  * Enforce strict action enum boundary values.
  * Check minimum confidence thresholds (e.g., immediate delivery during quiet hours requires calibrated confidence >= 0.80).
  * If validation fails: Inject fallback decision payload (`SUMMARIZE_LATER`, fallback priority 10).
* **Output**: `DecisionResult` payload.

### Stage 12: `Final Decision` Delivery & Async Audit Logging
* **Input**: `DecisionResult`.
* **Operation**:
  * Return final `DecisionResult` to client notification gateway synchronously.
  * Dispatch complete execution trace asynchronously to `DecisionLogger` (BigQuery / OpenTelemetry).
* **Output**: Notification routing action executed; async log stored.

---

## 3. Execution Paths & Performance Benchmarks

```
                                [Pipeline Start]
                                       │
                        ┌──────────────┴──────────────┐
                        │ Stage 5: Rule Engine Check │
                        └──────────────┬──────────────┘
                                       │
             ┌─────────────────────────┼─────────────────────────┐
             │ Rule Match (Bypass)     │ No Rule                 │ LLM Timeout/Error
             v                         v                         v
     ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
     │   FAST-PATH   │         │ STANDARD PATH │         │ FALLBACK PATH │
     │ (Deterministic)│        │  (LLM Reason) │         │ (Degraded)    │
     └───────┬───────┘         └───────┬───────┘         └───────┬───────┘
             │                         │                         │
     Latency: ~5 ms            Latency: ~250 ms          Latency: < 2 ms
     Confidence: 1.0           Confidence: Calibrated    Confidence: 0.50 (Default)
             │                         │                         │
             └─────────────────────────┼─────────────────────────┘
                                       │
                                       v
                           [Stage 12: Delivery & Log]
```

### Execution Path Comparison

| Metric / Feature | Fast-Path (Rule Bypass) | Standard Path (LLM Reasoner) | Fallback Path (System Recovery) |
| :--- | :--- | :--- | :--- |
| **Trigger Condition** | Level 0 or Level 1 Rule match | No rule match; system healthy | LLM timeout (>250ms), API crash, or validation failure |
| **Stages Executed** | 1 -> 2 -> 3 -> 4 -> 5 -> 9 -> 11 -> 12 | 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12 | 1 -> 2 -> 4 -> 5 -> 7(Fail) -> 11(Fallback) -> 12 |
| **Target Latency** | **< 5 ms** | **180 - 280 ms** | **< 2 ms** |
| **LLM Invocation** | NO | YES | FAILED / BYPASSED |
| **Confidence** | 0.95 - 1.00 | Calibrated (0.00 - 1.00) | 0.50 (System default) |

---

## 4. Fallback & Degradation Strategies

### 4.1. LLM Service Timeout & Outage Fallback
* **Condition**: `ReasoningService` fails to respond within 250 ms timeout budget or returns `HTTP 5xx` error.
* **Degradation Action**: Abort LLM wait immediately. Switch to **Fallback Path**:
  * If message sender is in user address book: Route as `DELIVER_SILENT`.
  * If message sender is unknown: Route as `SUMMARIZE_LATER`.
  * Set `DecisionMetadata.fallback_applied = True` and `fallback_reason = "LLM_SERVICE_TIMEOUT"`.

### 4.2. Low Calibrated Confidence Fallback
* **Condition**: `calibrated_confidence < 0.45` after Stage 9 calibration.
* **Degradation Action**: Overrule aggressive actions (`DELIVER_IMMEDIATELY` or `SUPPRESS_SPAM`).
  * Re-assign action to safe default: `DELIVER_SILENT` (for known contacts) or `BATCH_DIGEST` (for groups/unknowns).
  * Record `fallback_reason = "LOW_CONFIDENCE_RECOVERY"`.

### 4.3. Missing Signal or Evidence Fallback
* **Condition**: Upstream signal store or retrieval engine is unresponsive (`SignalBundle.is_degraded == True`).
* **Degradation Action**:
  * Execute standard `RuleEngine` using basic `MessageContext` metadata.
  * If no rule matches, bypass LLM and route as standard native notification (`DELIVER_IMMEDIATELY` during active hours, `DELIVER_SILENT` during quiet hours).

### 4.4. Complete Infrastructure Outage Safe Mode
* **Condition**: System-wide database or memory store disconnect.
* **Degradation Action**: Pass message directly to native OS notification tray without modification (`DELIVER_IMMEDIATELY` passthrough), ensuring zero dropped messages.
