# Decision Engine Architecture & Core Orchestration Blueprint

## 1. Overview & Architectural Role

The **Decision Intelligence Layer** serves as the central brain of the AI-powered WhatsApp Message Notification Router. It receives rich structured inputs from upstream layers—specifically `MessageContext`, `SignalBundle`, `EvidenceBundle`, `MediaContext`, `Historical Context`, `Business Context`, and `User Context`—and synthesizes them into an optimal, calibrated, and verifiable notification routing decision.

```
+---------------------------------------------------------------------------------------------------+
|                                     DECISION INTELLIGENCE LAYER                                   |
|                                                                                                   |
|  +---------------------+    +----------------------+    +--------------------------------------+  |
|  | DecisionFactory     |--->| DecisionContext      |--->| DecisionOrchestrator                 |  |
|  | (Context Ingestion) |    | (Consolidated Input) |    | (Execution Controller & Router)      |  |
|  +---------------------+    +----------------------+    +--------------------------------------+  |
|                                                                    |                              |
|                                            +-----------------------+-----------------------+      |
|                                            |                                               |      |
|                                            v                                               v      |
|                             +------------------------------+                +------------------+  |
|                             | RuleEngine                   |                | ReasoningService |  |
|                             | (Deterministic Fast-Path)    |                | (LLM Reasoner)   |  |
|                             +------------------------------+                +------------------+  |
|                                            |                                               |      |
|                                            +-----------------------+-----------------------+      |
|                                                                    |                              |
|                                                                    v                              |
|                                                     +------------------------------+              |
|                                                     | ConfidenceEngine             |              |
|                                                     | (Calibration & Adjustments)  |              |
|                                                     +------------------------------+              |
|                                                                    |                              |
|                                                                    v                              |
|                                                     +------------------------------+              |
|                                                     | DecisionValidator            |              |
|                                                     | (Schema & Logic Verifier)    |              |
|                                                     +------------------------------+              |
|                                                                    |                              |
|                                                                    v                              |
|  +---------------------+    +----------------------+    +--------------------------------------+  |
|  | DecisionLogger      |<---| Final Decision       |<---| DecisionResult                       |  |
|  | (Audit & Telemetry) |    | (Routing Action)     |    | (Calibrated & Verified Output)       |  |
|  +---------------------+    +----------------------+    +--------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

### Component Breakdown & Core Responsibilities

1. **`DecisionEngine`**: Top-level facade exposing the primary execution entry point (`evaluate(context)`). Manages lifecycle, error boundaries, and top-level telemetry.
2. **`DecisionFactory`**: Constructs an immutable, validated `DecisionContext` object by aggregating and normalizing raw contextual payload objects.
3. **`RuleEngine`**: Evaluates deterministic rules (safety, mutes, quiet hours, spam blacklists, explicit user preferences). Implements short-circuit evaluation for LLM bypass.
4. **`DecisionOrchestrator`**: Controls evaluation branching, coordinates data flow between deterministic rules and AI reasoners, injects evidence, and propagates uncertainty.
5. **`ReasoningService`**: Wraps the LLM Reasoner interface, formatting structured input frames and enforcing output contracts without executing raw prompt strings.
6. **`ConfidenceEngine`**: Calculates raw confidence, applies agreement/disagreement adjustment matrices, performs probability calibration, and quantifies uncertainty.
7. **`DecisionValidator`**: Performs multi-pass validation on the decision output (schema, allowed values, reasoning validity, factual grounding against `EvidenceBundle`).
8. **`DecisionLogger`**: Records structured decision audit traces, feature snapshots, latency breakdowns, and telemetry metrics asynchronously.

---

## 2. Decision Engine Architecture & Hierarchy

### Decision Hierarchy Levels

The decision engine operates across four explicit hierarchical levels. Higher levels take absolute precedence over lower levels.

```
+-------------------------------------------------------------------+  Priority
| Level 0: Deterministic Safety & Hard Overrides                    |  100 (Highest)
| - Threat detection, OTP bypass, explicit safety blocks            |
+-------------------------------------------------------------------+
| Level 1: Deterministic User & Business Rules                      |  80 - 99
| - Muted chats/groups, quiet hours, VIP bypass, blocklists         |
+-------------------------------------------------------------------+
| Level 2: Contextual LLM Reasoning                                 |  20 - 79
| - Ambiguous context, multi-signal synthesis, social relationship  |
+-------------------------------------------------------------------+
| Level 3: Fallback & Default Rules                                 |  0 - 19 (Lowest)
| - LLM timeout, validation failure, low confidence default action  |
+-------------------------------------------------------------------+
```

| Level | Level Name | Scope & Authority | Execution Latency | LLM Invocation |
| :--- | :--- | :--- | :--- | :--- |
| **Level 0** | Deterministic Safety | Critical security, self-harm, harassment, system alerts | < 1 ms | Bypassed |
| **Level 1** | Deterministic User/Business | User mutes, quiet hours, VIP overrides, rate limits | 1 - 5 ms | Bypassed |
| **Level 2** | Contextual LLM Reasoning | Urgency classification, intent analysis, summary routing | 150 - 300 ms | Invoked |
| **Level 3** | Fallback & Default | Service timeout, low confidence recovery, schema fix | < 2 ms | Bypassed |

### Priority Handling Matrix

Every rule and reasoning output is assigned a priority score between `0` and `100`:

* **`100`**: Critical Security / Emergency Safety Override. Instant execution.
* **`90 - 99`**: Hard User Constraints (Muted group, Muted sender, Explicit Quiet Hour rule without VIP exception).
* **`80 - 89`**: Soft User Constraints (VIP Contact Override during Quiet Hours, Transactional Payment Reminder).
* **`50 - 79`**: Standard AI Reasoner Outputs (Urgent work message, time-sensitive social planning, event updates).
* **`20 - 49`**: Low Urgency AI Reasoner Outputs (Casual chatter, promotional updates, repetitive forwards).
* **`0 - 19`**: System Fallbacks (Default silent batching on LLM failure or ultra-low confidence).

### Safety-First Reasoning Paradigm

Safety constraints override all probabilistic AI recommendations. If a message contains verified safety threats, phishing vectors, or severe harassment signals, the engine immediately triggers `SUPPRESS_SPAM` or `TRIGGER_EMERGENCY_OVERRIDE` depending on the risk type, completely ignoring downstream LLM recommendations and user personalization preferences.

### Human-Like Reasoning Capabilities

The decision engine mimics human cognitive prioritization by considering:
1. **Urgency vs. Importance Matrix**: Distinguishing between time-sensitive noise (e.g., promotional flash sale expiring) and quiet importance (e.g., non-urgent email summary from spouse).
2. **Social Context Awareness**: Factoring in historical response time to a specific sender, relationship closeness score, and group chat dynamics.
3. **Temporal Sensitivity**: Understanding time-bound windows (e.g., a message asking "Are you free for lunch in 10 mins?" vs. "Let's catch up next month").
4. **Cognitive Load Optimization**: Preventing notification fatigue during active work status by batching semi-important updates into periodic summaries.

---

## 3. Decision Orchestration & Interaction

### Module Communication & Data Flow

Modules communicate synchronously via strongly typed interfaces, passing immutable data wrappers (`DecisionContext`, `RuleEvaluationResult`, `ReasoningOutput`, `CalibratedDecision`).

```
DecisionContext
      |
      v
RuleEngine.evaluate()
      |
      +---> Rule Triggered? (Level 0 / Level 1)
      |         |
      |         +---> YES: Short-circuit -> Bypass LLM -> ConfidenceEngine -> OutputValidator
      |         |
      |         +---> NO: Continue to LLM Path
      v
DecisionOrchestrator.prepare_reasoner_frame()
      |
      v
ReasoningService.evaluate()
      |
      v
ConfidenceEngine.calibrate()
      |
      v
DecisionValidator.validate()
      |
      +---> Valid?
      |       |
      |       +---> YES: Final Decision Output
      |       +---> NO: Trigger Recovery -> Apply Fallback
      v
DecisionLogger.log_async()
```

### Evidence Injection Mechanism

Relevant facts from `EvidenceBundle` (retrieved via BM25/Vector search from past conversation history, calendar items, or reference documents) are injected into the orchestrator frame:
* **Factual Grounding**: Direct matches between current message topics and active user commitments (e.g., a calendar appointment at 3:00 PM referenced in the incoming text).
* **Context Verification**: Validating claimed identity or past promises against stored conversation history.
* **Weighted Relevance**: Evidence items carry relevance scores (0.0 to 1.0) that directly modify the confidence score generated by the LLM reasoner.

### Personalization Influence Model

Personalization modifies decision boundaries without breaking hard safety rules:
* **Relationship Weighting**: Messages from senders with high `relationship_closeness_score` (>0.8) lower the urgency threshold required for immediate delivery.
* **Historical Interaction Velocity**: Senders whose messages the user historically opens within 30 seconds receive an urgency boost (+0.15).
* **Topic Affinity**: Senders or groups matching user's active interest vector bypass silent batching unless explicitly muted.

### Uncertainty Propagation Framework

Uncertainty accumulates through the pipeline:
1. **Input Signal Uncertainty**: Noise in sentiment, urgency, or relationship signals propagates to `DecisionContext.signal_uncertainty`.
2. **Evidence Uncertainty**: Low vector similarity scores in `EvidenceBundle` reduce grounding confidence.
3. **Reasoning Uncertainty**: Entropy in LLM token probabilities or conflicting signal vectors reduces raw model confidence.
4. **Cumulative Calibration**: `ConfidenceEngine` aggregates input, evidence, and model uncertainty into a single `calibrated_confidence` score. If total uncertainty exceeds `0.45`, the decision defaults to a safe fallback (`SUMMARIZE_LATER` or `DELIVER_SILENT`).

---

## 4. Conflict Resolution Matrix

When inputs or sub-systems contradict each other, the orchestrator applies deterministic resolution rules:

```
+-------------------------------------------------------------------------------------------------------+
| CONFLICT TYPE            | CONFLICTING ELEMENTS               | RESOLUTION STRATEGY                   |
+--------------------------+------------------------------------+---------------------------------------+
| Rule vs. LLM             | Rule says MUTE, LLM says DELIVER   | Rule WINS unconditionally (Level 1)   |
| Rule vs. LLM             | Safety Rule says BLOCK, LLM ALLOW  | Safety Rule WINS (Level 0)            |
| Signal Disagreement      | Urgency = HIGH, Trust = LOW        | Treat as Potential Scam / Verification|
| Signal Disagreement      | Spam Score = HIGH, VIP Contact = TRUE| VIP Contact WINS, downgrade spam alert|
| Evidence Conflict        | Document A supports, Doc B denies | Weight by recency & source authority |
| Low Confidence           | Calibrated Confidence < 0.50       | Fallback to DELIVER_SILENT / BATCH    |
| Sparse Context           | Zero history, zero signals         | Default to standard WhatsApp behavior |
| Contradictory History    | User historically muted & unmuted  | Use most recent 7-day trend           |
+--------------------------+------------------------------------+---------------------------------------+
```

### Conflict Resolution Protocols

1. **Rule vs. LLM Resolution**:
   * **Rule Supremacy Principle**: No probabilistic AI output can override a Level 0 or Level 1 deterministic rule.
   * Exception: Emergency Bypass Rules specifically design conditions where high-urgency keywords from starred contacts break Quiet Hours.

2. **Signal Disagreement Resolution**:
   * If `urgency_score > 0.8` but `trust_score < 0.3`, route to `DELIVER_SILENT` with a visual risk flag, preventing immediate interruption while preserving access.
   * If `spam_score > 0.7` but sender is in user address book, suppress spam alert, clear spam flag, and evaluate under standard rules.

3. **Conflicting Evidence Resolution**:
   * When retrieved evidence items contain contradictory facts, rank evidence items by `timestamp` (recency) and `authority_level` (explicit user preference > group message text).

4. **Sparse Context Resolution**:
   * In cold-start scenarios (new user, empty message history, missing signals), the engine disables complex personalization weighting and applies a default rule set matching native device notification behavior.

---

## 5. LLM Reasoner Architecture (Prompt-Free Specification)

The `ReasoningService` abstracts the LLM reasoner component. It receives a structured context payload and produces a structured reasoning response without exposing prompt strings or implementation details.

### System Responsibilities
* Analyze complex, ambiguous, or multimodal message content where deterministic rules cannot make a high-confidence determination.
* Synthesize text, media summary, user context, historical interaction patterns, and retrieved evidence into a coherent rationale.
* Assign structured scores for urgency, importance, and recommended routing action.

### Structural Inputs
The LLM Reasoner consumes a normalized context frame containing:
* **Message Payload**: Text string, media captions, language code, structural metadata.
* **Aggregated Signals**: Calculated scores for urgency, sentiment, trust, relationship closeness, spam probability, and quiet hours status.
* **Contextual Grounding**: Relevant facts extracted from `EvidenceBundle` (up to top-5 grounded context snippets).
* **User & Relationship Context**: Sender relationship tier, historical response latency, user current status (e.g., `IN_MEETING`, `DRIVING`, `AVAILABLE`).
* **Temporal Context**: Local time, day of week, active schedule events.

### Structural Outputs
The LLM Reasoner returns a strictly typed JSON output payload matching:
* `proposed_action`: Action enum (`DELIVER_IMMEDIATELY`, `DELIVER_SILENT`, `SUMMARIZE_LATER`, `BATCH_DIGEST`, `SUPPRESS_SPAM`, `SUPPRESS_MUTE`, `TRIGGER_EMERGENCY_OVERRIDE`).
* `urgency_rating`: Normalized float (`0.0` to `1.0`).
* `importance_rating`: Normalized float (`0.0` to `1.0`).
* `reasoning_summary`: Concise natural language explanation (max 250 characters).
* `key_factors`: Array of primary factors driving the recommendation (e.g., `["VIP_CONTACT", "TIME_SENSITIVE_ASK", "ACTIVE_MEETING"]`).
* `raw_confidence`: Model self-assessed confidence score (`0.0` to `1.0`).

### Step-by-Step Reasoning Process

```
Step 1: Parse Input Context Frame
  └─ Extract message payload, signals, evidence grounding, user status, and relationship tier.

Step 2: Social & Safety Alignment
  └─ Verify sender credibility against relationship tier and trust signals.

Step 3: Temporal & User State Evaluation
  └─ Compare message time-sensitivity against current user state (e.g., meeting, driving, quiet hours).

Step 4: Evidence Grounding Check
  └─ Validate if message references existing commitments, calendar items, or ongoing threads.

Step 5: Action Synthesis & Score Generation
  └─ Select recommended routing action, compute urgency/importance scores, and format structured summary rationale.
```

---

## 6. Architectural Dependencies & Component Layout

```
                  +-----------------------------------+
                  |           DecisionEngine          |
                  +-----------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
            v                       v                       v
  +------------------+    +-------------------+   +--------------------+
  | DecisionFactory  |    | RuleEngine        |   |DecisionOrchestrator|
  +------------------+    +-------------------+   +--------------------+
                                                            |
                                    +-----------------------+-----------------------+
                                    |                       |                       |
                                    v                       v                       v
                          +-------------------+   +-------------------+   +------------------+
                          | ReasoningService  |   | ConfidenceEngine  |   |DecisionValidator |
                          +-------------------+   +-------------------+   +------------------+
                                                                                    |
                                                                                    v
                                                                          +-------------------+
                                                                          |  DecisionLogger   |
                                                                          +-------------------+
```

### Component Lifecycle & Dependency Flow
1. `DecisionEngine` is instantiated as a singleton, injecting `RuleEngine`, `DecisionOrchestrator`, `ConfidenceEngine`, `DecisionValidator`, and `DecisionLogger`.
2. On message event receipt, `DecisionFactory` builds an immutable `DecisionContext`.
3. `DecisionEngine` passes `DecisionContext` to `RuleEngine`.
4. If a deterministic rule fires with LLM bypass flag, execution jumps directly to `ConfidenceEngine`.
5. If no bypass rule fires, `DecisionOrchestrator` invokes `ReasoningService`.
6. Output flows through `ConfidenceEngine` for calibration.
7. Calibrated output is checked by `DecisionValidator`. If validation fails, fallback policy resolves to a safe action.
8. Final `DecisionResult` is returned to caller, and `DecisionLogger` writes async audit logs.
