# Signal Quality & Reliability Specification

## 1. Executive Summary & Quality Framework

The **Signal Quality Engine** evaluates the trustworthiness, mathematical completeness, and reliability of every computed signal in the `SignalBundle`.

Because real-world message payloads may suffer from OCR errors, missing contact synchronization, network latency, or corrupted metadata, the Signal Quality Engine ensures that downstream consumers never consume unreliable signals without explicit confidence metrics.

---

## 2. Master Signal Quality Metrics

Every signal $s$ computed by the engine is assigned three quality attributes:
$$\text{QualityTuple}(s) = \langle S_s, C_s, R_s \rangle$$

```
                                  [ Message Context ]
                                           │
                                           ▼
                       ┌──────────────────────────────────────┐
                       │       Signal Calculation ($S_s$)      │
                       └──────────────────────────────────────┘
                                           │
       ┌───────────────────────────────────┼───────────────────────────────────┐
       ▼                                   ▼                                   ▼
┌──────────────┐                   ┌──────────────┐                    ┌──────────────┐
│  Confidence  │                   │ Completeness │                    │ Reliability  │
│    ($C_s$)   │                   │  ($Q_{comp}$)│                    │    ($R_s$)   │
└──────────────┘                   └──────────────┘                    └──────────────┘
       │                                   │                                   │
       └───────────────────────────────────┼───────────────────────────────────┘
                                           │
                                           ▼
                       ┌──────────────────────────────────────┐
                       │   Conflict Resolution & Imputation   │
                       └──────────────────────────────────────┘
                                           │
                                           ▼
                                 [ Frozen SignalValue ]
```

### 2.1 Signal Confidence ($C_s \in [0.0, 1.0]$)
Quantifies certainty in the calculated score based on upstream source reliability, model output probabilities, and feature missingness:

$$C_s = \prod_{i \in \text{Inputs}(s)} c(f_i) \cdot \text{Decay}(\Delta t)$$

Where:
- $c(f_i)$ is the individual input feature completeness/accuracy ($1.0$ if present, $0.0$ if missing).
- $\text{Decay}(\Delta t) = \exp(-\gamma \Delta t)$ represents temporal decay for cached metrics.

---

### 2.2 Signal Completeness ($Q_{comp} \in [0.0, 1.0]$)
Measures the structural coverage of expected signals across all 11 category blocks:

$$Q_{comp} = \frac{\sum_{i=1}^{N} \mathbb{I}(s_i \neq \text{NULL})}{N}$$

Where $N = 20+$ total defined system signals.

---

### 2.3 Signal Reliability ($R_s \in [0.0, 1.0]$)
Evaluates historical stability and resistance of the signal to noise or adversarial perturbation:

$$R_s = 1.0 - \min\left(1.0, \frac{\text{Var}(S_s)}{\sigma^2_{\max}}\right)$$

---

## 3. Missing Signal Handling Protocols

When an input feature or sub-context is missing (e.g. `BusinessContext` absent because sender is a peer), the engine enforces deterministic missing signal handling:

### 3.1 Null Object Fallback Pattern
The engine never returns null or undefined for any signal score. Missing signals instantiate a deterministic Default Fallback `SignalValue`:
```
SignalValue(
    score = 0.0,
    confidence = 0.0,
    explainability = SignalExplainability(
        raw_value = 0.0,
        primary_driver = "NONE",
        rationale = "Default Null-Object Imputation due to missing input context.",
        contributing_factors = {}
    )
)
```

### 3.2 Category-Level Graceful Degradation
- **Missing Multimodal Data** (e.g., OCR engine timeout): Media signals degrade gracefully to $score = 0.10, confidence = 0.20$, allowing text-based risk and urgency calculators to run unaffected.
- **Missing History Data** (e.g., brand new user): Behavioral and history signals fall back to global population medians with $confidence = 0.30$.

---

## 4. Conflicting Signal Handling Protocols

When two signals emit contradictory values (e.g., High Urgency vs High Scam Risk, or High Trust vs High Spam Score), the engine applies deterministic arbitration rules.

### 4.1 Confidence-Weighted Balancing Formula
For conflicting signals $A$ and $B$, the unified balanced score is calculated as:

$$S_{balanced} = \frac{C_A \cdot S_A + C_B \cdot S_B}{C_A + C_B}$$

### 4.2 Signal Arbitration Matrix

| Signal A (Score High) | Signal B (Score High) | Primary Conflict Hazard | Arbitration Rule & Output Resolution |
| :--- | :--- | :--- | :--- |
| **High Urgency** ($S_{urg} \ge 0.8$) | **High Scam Risk** ($S_{scam} \ge 0.7$) | Phishing hook mimicking urgent distress. | **Risk Trumps Urgency**: Suppress urgency confidence ($C_{urg} \to 0.2$), preserve Scam Risk ($S_{scam} = 0.9$). |
| **High Business Trust** ($S_{trust} \ge 0.9$) | **High Spam Score** ($S_{spam} \ge 0.8$) | Compromised official business account sending bulk promo. | **Spam Dampening**: Lower trust score to $0.40$; mark business risk flag. |
| **High Relationship** ($S_{rel} \ge 0.85$) | **Unknown Sender Risk** ($S_{unk} \ge 0.8$) | Desynchronized contact book sync. | **Trust Trumps Unknown**: Contact history overrides unsaved number status ($S_{unk} \to 0.10$). |
| **Quiet Hours Active** ($S_{quiet} = 1.0$) | **High Emergency** ($S_{emerg} \ge 0.9$) | Life safety alert during sleep window. | **Emergency Trumps Quiet Hours**: Emergency score preserved; quiet hours flagged for downstream bypass. |

---

## 5. Signal Quality Monitoring Schema

The `SignalQualityMetrics` summary is attached to the final `SignalBundle`:

```
SignalQualityMetrics
├── total_signals_computed: Int          # Total active calculated signals (Target: 20)
├── global_completeness_score: Float     # Overall completeness fraction [0.0, 1.0]
├── global_average_confidence: Float     # Weighted mean confidence score [0.0, 1.0]
├── degraded_signal_count: Int           # Count of signals operating on fallback defaults
├── conflicting_signal_count: Int        # Count of arbitrated signal pairs
└── quality_warning_flags: List<String>  # Audit warning strings (e.g. "LOW_MEDIA_CONFIDENCE")
```
