# Confidence Engine: Calculation, Calibration & Uncertainty Management

## 1. Overview & Mathematical Formulation

The **Confidence Engine** computes, calibrates, and verifies numerical confidence for every notification routing decision. It converts raw model probability outputs into well-calibrated posterior probabilities, penalizing signal contradictions and evidence gaps to guarantee predictable system reliability.

```
+-----------------------------------------------------------------------------------------------+
|                                    CONFIDENCE ENGINE PIPELINE                                 |
|                                                                                               |
|   Raw LLM Confidence (C_raw) OR Rule Confidence (1.0)                                         |
|          │                                                                                    |
|          v                                                                                    |
|   +---------------------------------------------------------------------------------------+   |
|   | Signal Agreement Adjustment (S_adj)                                                   |   |
|   | - Signal Agreement: +0.15 to +0.25                                                    |   |
|   | - Signal Disagreement: -0.20 to -0.40                                                 |   |
|   +---------------------------------------------------------------------------------------+   |
|          │                                                                                    |
|          v                                                                                    |
|   +---------------------------------------------------------------------------------------+   |
|   | Context & Evidence Adjustment (E_adj)                                                 |   |
|   | - Evidence Weak/Missing: -0.15 to -0.30                                               |   |
|   | - History Missing: -0.10                                                              |   |
|   | - Media Corrupted: -0.15                                                              |   |
|   +---------------------------------------------------------------------------------------+   |
|          │                                                                                    |
|          v                                                                                    |
|   +---------------------------------------------------------------------------------------+   |
|   | Temperature Scaling & Calibration (Platt Model)                                       |   |
|   | - Calibrated Confidence = Sigmoid((Logit(C_raw + S_adj + E_adj)) / T)                |   |
|   +---------------------------------------------------------------------------------------+   |
|          │                                                                                    |
|          v                                                                                    |
|   Calibrated Confidence (C_calibrated) -> Enforce Decision Thresholds                         |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Base Confidence Computation Model

### Base Confidence Formula
The preliminary uncalibrated confidence $C_{\text{base}}$ is calculated as:

$$C_{\text{base}} = C_{\text{raw}} + S_{\text{adj}} + E_{\text{adj}} + H_{\text{adj}}$$

Where:
* $C_{\text{raw}}$: Self-assessed raw confidence from the LLM Reasoner ($0.0 \le C_{\text{raw}} \le 1.0$), or $1.0$ for Level 0 Deterministic Rules.
* $S_{\text{adj}}$: Signal agreement/disagreement adjustment factor.
* $E_{\text{adj}}$: Evidence grounding adjustment factor.
* $H_{\text{adj}}$: Historical context completeness adjustment factor.

---

## 3. Confidence Adjustment Matrix

The confidence score dynamically increases or decreases based on signal alignment and data availability:

| Condition / Scenario | Factor Code | Adjustment Value | Mathematical Condition | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **High Signal Agreement** | $S_{\text{agree}}$ | **+0.15 to +0.25** | Urgency, Sentiment, and Trust signals align in same direction (std_dev < 0.15). | High multi-signal congruence increases decision certainty. |
| **Severe Signal Contradiction** | $S_{\text{disagree}}$ | **-0.20 to -0.40** | Urgency > 0.85 BUT Trust < 0.30 OR Spam > 0.70 BUT VIP = True. | Conflicting indicators signify ambiguity or potential scam vectors. |
| **Deterministic Rule Fired** | $R_{\text{override}}$ | **Override = 1.0** | Level 0 Safety Rule matches (`bypass_llm == True`). | Hard safety rules operate with absolute deterministic authority. |
| **User Mute Rule Fired** | $R_{\text{mute}}$ | **Override = 0.95** | Level 1 User Mute Rule matches. | Hard user mute setting operates with near-perfect certainty. |
| **Weak / Missing Evidence** | $E_{\text{weak}}$ | **-0.15 to -0.30** | Top evidence relevance score < 0.40 or zero retrieved snippets. | Lack of factual context reduces grounding confidence. |
| **Missing History Context** | $H_{\text{missing}}$ | **-0.10** | Cold start; zero past interaction history for sender. | Unseen sender introduces behavioral uncertainty. |
| **Media Unavailable / Corrupted**| $M_{\text{corrupt}}$ | **-0.15** | Message includes image/voice attachment that failed processing. | Unanalyzed multimodal payload reduces complete context vision. |

---

## 4. Confidence Calibration Pipeline

Raw neural network outputs are notoriously overconfident. The `ConfidenceEngine` applies post-hoc probability calibration to map raw model scores to true empirical accuracy.

```
Raw Score (0.92)  ──► [Temperature Scaling: T = 1.45] ──► Calibrated Score (0.78)
```

### 4.1. Temperature Scaling Model
Temperature scaling rescales logits without altering classification argmax rankings:

$$\sigma_{\text{calibrated}}(z) = \frac{1}{1 + e^{-z / T}}$$

Where $z = \text{logit}(C_{\text{base}})$ and $T$ is the learned system temperature parameter (tuned offline using validation log-loss, typically $T \approx 1.35 - 1.50$).

### 4.2. Platt Scaling Formulation
For binary routing decisions (e.g., Immediate Delivery vs. Suppress):

$$P(\text{Correct} \mid C_{\text{base}}) = \frac{1}{1 + e^{A \cdot C_{\text{base}} + B}}$$

Parameters $A$ and $B$ are fit via maximum likelihood estimation over historical user feedback logs (notification clicks vs. dismissals).

---

## 5. Dynamic Decision Thresholding

Routing actions require calibrated confidence to meet strict minimum thresholds:

```
+-----------------------------------------------------------------------------------------------+
| ACTION                         | MINIMUM REQUIRED CONFIDENCE | FALLBACK IF BELOW THRESHOLD     |
+--------------------------------+-----------------------------+---------------------------------+
| TRIGGER_EMERGENCY_OVERRIDE     | 0.90                        | DELIVER_IMMEDIATELY             |
| DELIVER_IMMEDIATELY            | 0.70 (0.85 during Quiet Hrs)| DELIVER_SILENT                  |
| SUPPRESS_SPAM                  | 0.85                        | DELIVER_SILENT (with Spam Tag)  |
| SUMMARIZE_LATER                | 0.55                        | BATCH_DIGEST                    |
| DELIVER_SILENT                 | 0.45                        | BATCH_DIGEST                    |
+--------------------------------+-----------------------------+---------------------------------+
```

If a proposed action fails to reach its required minimum confidence threshold, the engine automatically downgrades the action to its mapped safe fallback.

---

## 6. Uncertainty Propagation Framework

Uncertainty is categorized into two distinct forms and handled accordingly:

```
Total Uncertainty (U_total) = Aleatoric Uncertainty (U_aleatoric) + Epistemic Uncertainty (U_epistemic)
```

1. **Aleatoric Uncertainty (Data Noise)**:
   * Arises from inherently ambiguous message phrasing (e.g., "See you whenever").
   * *Handling*: Route to `DELIVER_SILENT` or `SUMMARIZE_LATER` to prevent unnecessary user alert interruptions.
2. **Epistemic Uncertainty (Model / Knowledge Deficit)**:
   * Arises from missing evidence, unparsed voice note, or unverified sender.
   * *Handling*: Fallback to standard deterministic user rules and log feature gap for model retraining.
