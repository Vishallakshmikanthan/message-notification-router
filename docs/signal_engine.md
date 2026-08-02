# Signal Computation Engine Architecture & Pipeline Specification

## 1. Executive Summary & Engine Objectives

The **Signal Computation Engine** is the deterministic analytical core of the WhatsApp Message Notification Router. It receives a fully populated, immutable `MessageContext` object (produced by Phase 5: Context Assembly Engine) and transforms raw features, multimodal extractions, historical metrics, and relationship graphs into a collection of interpretable, explainable continuous signals ($0.0 \le S \le 1.0$) encapsulated in a frozen `SignalBundle`.

### Core Architectural Guarantees
1. **Strict Non-Decisional Guarantee**: The Signal Engine computes domain signals *only*. It performs **zero notification routing decisions** (e.g., notify, digest, mute), **zero output generation**, and **zero LLM prompt execution**.
2. **Determinism & Idempotency**: Given identical `MessageContext` inputs, the Signal Engine guarantees identical `SignalBundle` outputs with zero side effects.
3. **Pure Functionality**: All individual calculators operate as stateless transformation functions over context fields.
4. **End-to-End SLA**: Complete signal processing pipeline executes within $\le 15 \text{ ms}$ at 99.9th percentile latency.

---

## 2. Complete Processing Pipeline Architecture

```
                                  [ MessageContext ]
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 1: Context Validation   │
                         └─────────────────────────────────┘
                                          │
                                          ▼
  ┌───────────────────────────────────────────────────────────────────────────────┐
  │                           PARALLEL EXECUTION DAG                              │
  │                                                                               │
  │  ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────┐  │
  │  │ Stage 2: Behaviour    │  │ Stage 3: Relationship │  │ Stage 4: Trust    │  │
  │  └───────────────────────┘  └───────────────────────┘  └───────────────────┘  │
  │              │                          │                        │            │
  │              ▼                          ▼                        ▼            │
  │  ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────┐  │
  │  │ Stage 5: Urgency      │  │ Stage 6: Risk         │  │ Stage 7: Business │  │
  │  └───────────────────────┘  └───────────────────────┘  └───────────────────┘  │
  │              │                          │                        │            │
  │              ▼                          ▼                        ▼            │
  │  ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────┐  │
  │  │ Stage 8: Notification  │  │ Stage 9: Historical   │  │ Stage 10: Temporal│  │
  │  └───────────────────────┘  └───────────────────────┘  └───────────────────┘  │
  └───────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 11: Signal Quality &    │
                         │          Normalization          │
                         └─────────────────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Stage 12: Signal Aggregation  │
                         └─────────────────────────────────┘
                                          │
                                          ▼
                                   [ SignalBundle ]
```

---

## 3. Comprehensive Stage-by-Stage Pipeline Breakdown

### Stage 1: Context Validation & Quality Pre-Check
- **Component**: `SignalValidator`
- **Responsibility**: Inspects incoming `MessageContext` schema integrity, verifies presence of critical identifier fields (`message_id`, `sender_id`, `receiver_id`), checks metadata completeness score ($Q_{comp} \ge 0.50$), and marks missing optional sub-contexts for graceful degradation.
- **Output**: Validated `MessageContext` envelope with Context Integrity Flag vector.

### Stage 2: Behaviour Analysis
- **Component**: `BehaviourEngine`
- **Responsibility**: Computes user interaction dynamics, reading responsiveness, historical reply velocities, dismiss propensities, and notification ignore patterns.
- **Inputs**: `MessageContext.notification_behaviour`, `MessageContext.behaviour_stats`.

### Stage 3: Relationship Analysis
- **Component**: `TrustEngine` (Relationship Calculators)
- **Responsibility**: Computes tie strength, intimacy score, two-way message symmetry, interaction frequency, and direct contact status between sender and recipient.
- **Inputs**: `MessageContext.relationship`, `MessageContext.conversation`.

### Stage 4: Trust Analysis
- **Component**: `TrustEngine`
- **Responsibility**: Computes known contact baseline, group structural reliability, historical user trust rating, and business verification level.
- **Inputs**: `MessageContext.sender`, `MessageContext.business`, `MessageContext.group`.

### Stage 5: Urgency Analysis
- **Component**: `UrgencyEngine`
- **Responsibility**: Evaluates time sensitivity, emergency triggers, health/family crises, meeting/appointment notifications, payment deadlines, and critical operational announcements.
- **Inputs**: `MessageContext.core_message`, `MessageContext.media`, `MessageContext.temporal_info`.

### Stage 6: Risk Analysis
- **Component**: `RiskEngine`
- **Responsibility**: Evaluates spam probability, scam patterns, financial fraud indicators, forward-chain virality risk, unknown sender hazard, visual text scam, and acoustic voice scam risk.
- **Inputs**: `MessageContext.core_message`, `MessageContext.media`, `MessageContext.sender`.

### Stage 7: Business Analysis
- **Component**: `TrustEngine` & `PersonalizationEngine` (Business Calculators)
- **Responsibility**: Calculates commercial intent score, transactional vs promotional distinction, business interaction history, and business trust rating.
- **Inputs**: `MessageContext.business`, `MessageContext.relationship`.

### Stage 8: Notification Analysis
- **Component**: `BehaviourEngine` (Notification Load Calculators)
- **Responsibility**: Evaluates current notification volume, hourly delivery density, user notification fatigue index, and alert burst thresholds.
- **Inputs**: `MessageContext.notification_behaviour`.

### Stage 9: Historical Analysis
- **Component**: `PersonalizationEngine` (Historical Calculators)
- **Responsibility**: Computes long-term open rates, historical response latencies, multi-day engagement trends, and contact preference trajectories.
- **Inputs**: `MessageContext.history`.

### Stage 10: Temporal Analysis
- **Component**: `PersonalizationEngine` (Temporal Calculators)
- **Responsibility**: Evaluates local time context, user quiet hours status, weekend vs weekday behavioral shifts, and current time-of-day affinity.
- **Inputs**: `MessageContext.temporal_info`, `MessageContext.receiver`.

### Stage 11: Signal Quality & Normalization
- **Component**: `SignalNormalizer` & `SignalQualityEngine`
- **Responsibility**: Applies min-max or logistic sigmoid scaling to bound all raw scores strictly to $[0.0, 1.0]$, assesses per-signal confidence ($C_s$), missing signal imputation, and handles conflicting signals via dampening functions.

### Stage 12: Signal Aggregation & Assembly
- **Component**: `SignalAggregator` & `SignalFactory`
- **Responsibility**: Bundles all category signals, calculates global confidence ($C_{global}$) and global completeness ($Q_{global}$), attaches processing latency metadata, freezes nested objects, and returns the immutable `SignalBundle`.

---

## 4. Architectural Component Specification

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    SIGNAL ENGINE                                       │
│                                                                                        │
│   ┌─────────────────┐    ┌─────────────────┐    ┌──────────────────────────────────┐   │
│   │ SignalRegistry  │───▶│  SignalFactory  │───▶│         SignalCalculator         │   │
│   └─────────────────┘    └─────────────────┘    │  (Abstract Base & Derived Units) │   │
│                                                 └──────────────────────────────────┘   │
│                                                                  │                     │
│   ┌─────────────────┐    ┌─────────────────┐                     ▼                     │
│   │ SignalValidator │    │SignalNormalizer │    ┌──────────────────────────────────┐   │
│   └─────────────────┘    └─────────────────┘    │         SignalAggregator         │   │
│                                                 └──────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 `SignalEngine` (Master Orchestrator)
- **Role**: Entry point and DAG execution orchestrator.
- **Responsibilities**:
  - Manages thread pool for parallel signal calculation.
  - Controls lifecycle from validation to aggregation.
  - Enforces execution timeout boundaries ($15 \text{ ms}$).

### 4.2 `SignalCalculator` (Abstract Calculator Interface)
- **Role**: Base interface implemented by all 20+ signal calculation units.
- **Contract**:
  - `calculate(context: MessageContext) -> RawSignalValue`
  - `getName() -> String`
  - `getDependencies() -> List<String>`

### 4.3 `SignalAggregator` (Bundle Assembler)
- **Role**: Combines individual normalized signal scores into category signal objects and packages the final container.
- **Responsibilities**:
  - Computes bundle-level metadata (`bundle_id`, `computed_at`, `calculation_latency_ms`).
  - Computes global signal confidence ($C_{global}$) and global completeness ($Q_{global}$).

### 4.4 `SignalValidator` (Data Integrity Auditor)
- **Role**: Enforces structural contracts on incoming `MessageContext` and outgoing `SignalBundle`.
- **Validation Checks**:
  - Rejects contexts with missing primary keys.
  - Verifies all signal scores fall strictly within $[0.0, 1.0]$.
  - Verifies presence of non-null rationale strings for all active signals.

### 4.5 `SignalNormalizer` (Mathematical Bounding Engine)
- **Role**: Normalizes raw domain values into uniform continuous probabilities using standard mathematical transforms:
  - **Logistic Sigmoid**: $S = \frac{1}{1 + e^{-k(x - x_0)}}$
  - **Min-Max Scaling**: $S = \frac{\min(\max(x, x_{\min}), x_{\max}) - x_{\min}}{x_{\max} - x_{\min}}$

### 4.6 `SignalFactory` (Object Instantiation Unit)
- **Role**: Constructs standardized, immutable signal data objects, ensuring thread-safe instance reusability and default value injection.

### 4.7 `SignalRegistry` (Dynamic Calculator Directory)
- **Role**: Maintains reference map of registered calculators, validates execution DAG topology, and ensures zero circular dependencies between signals.

---

## 5. Dependency Flow & Execution Lifecycle

```
[ Context Received ]
        │
        ▼
[ SignalValidator.validateContext() ]
        │
        ├──▶ Failure: [ Inject Null-Object Fallbacks & Flag Degradation ]
        │
        ▼
[ SignalRegistry.getExecutionPlan() ]
        │
        ├──▶ Phase 1 Parallel Execution (Base Calculators):
        │    ├── RiskCalculators (Spam, Scam, Fraud)
        │    ├── UrgencyCalculators (Emergency, Event, Payment)
        │    ├── TrustCalculators (Business, Contact, Group)
        │    ├── BehaviourCalculators (Fatigue, Read, Reply)
        │    └── TemporalCalculators (Quiet Hours, Time of Day)
        │
        ├──▶ Phase 2 Parallel Execution (Derived Personalization Calculators):
        │    ├── PersonalizationEngine (Relevance, Preferences, Importance)
        │    └── Conflict Resolver & Signal Normalizer
        │
        ▼
[ SignalAggregator.assembleBundle() ]
        │
        ▼
[ SignalFactory.freezeAndDeliver() ] ──▶ [ Immutable SignalBundle ]
```

---

## 6. Scalability, Performance & Reliability Blueprint

### 6.1 Latency SLA & Parallel Execution
- **Parallelization Strategy**: Independent category calculators (Risk, Urgency, Trust, Behaviour, Temporal) execute concurrently across a bounded worker thread pool.
- **Short-Circuit Thresholds**: If context validation indicates severe corruption ($Q_{comp} < 0.20$), signal computation short-circuits instantly, returning a low-confidence baseline bundle within $< 1 \text{ ms}$.

### 6.2 Stateless Design & Horizontal Scaling
- The `SignalEngine` maintains **zero mutable internal state**. Every node in a distributed microservice pool can process any incoming `MessageContext` independently without inter-node state synchronization.

---

## 7. Production Best Practices & Architectural Guidelines

### 7.1 Signal Independence & Overlap Prevention
- **Distinct Mathematical Models**: Each signal must measure a distinct psychological, relational, or risk dimension. For example:
  - `urgency` measures *time criticality* ($0.0 \le U \le 1.0$).
  - `relevance` measures *user interest alignment* ($0.0 \le R \le 1.0$).
  - `relationship_strength` measures *social proximity* ($0.0 \le S \le 1.0$).
- High urgency does not imply high relevance or high relationship strength. Keeping these dimensions orthogonal prevents compound error propagation.

### 7.2 Explainability Standard
- Every computed signal MUST output an accompanying `SignalExplainability` record containing:
  - `raw_value`: Exact raw numerical metric prior to normalization.
  - `normalized_score`: Bounded score in $[0.0, 1.0]$.
  - `confidence`: Certainty score in $[0.0, 1.0]$.
  - `primary_driver`: Feature name that contributed most heavily to the calculation.
  - `rationale`: Human-readable natural language summary of the calculation logic.

### 7.3 Testing Strategy
- **Unit Tests**: Test each `SignalCalculator` against boundary context inputs (e.g., zero historical messages, maximum forward count, missing media metadata).
- **Property-Based Testing**: Verify invariants ($0.0 \le S \le 1.0$, $0.0 \le C \le 1.0$) across millions of synthetically generated context combinations.
- **Regression Fixtures**: Maintain snapshot test suites for canonical message scenarios (e.g., family emergency, banking OTP, spam broadcast, work group assignment).
