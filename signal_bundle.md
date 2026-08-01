# Master SignalBundle Schema & Data Specification

## 1. Executive Summary & Master Schema Overview

The `SignalBundle` is the single, immutable data contract emitted by the Signal Computation Engine. It collects all calculated category signals, score normalized metrics, confidence ratings, and explainability records into a structured, frozen container. 

Downstream decision-making modules consume the `SignalBundle` to evaluate notification policies, priority rankings, and delivery schedules without recomputing feature logic.

### Master Hierarchy
```
SignalBundle Container
│
├── metadata: SignalBundleMetadata
├── behaviour: BehaviourSignals
├── risk: RiskSignals
├── trust: TrustSignals
├── urgency: UrgencySignals
├── relationship: RelationshipSignals
├── business: BusinessSignals
├── group: GroupSignals
├── history: HistorySignals
├── temporal: TemporalSignals
├── media: MediaSignals
└── conversation: ConversationSignals
```

---

## 2. Standardized Atomic `SignalValue` Envelope

Every individual signal score inside the `SignalBundle` is wrapped in a standard `SignalValue` container to guarantee uniform score bounding, confidence estimation, and auditability.

### `SignalValue` Schema
```
SignalValue
├── score: Float                         # Bounded score in range [0.0, 1.0]
├── confidence: Float                    # Metric confidence score in range [0.0, 1.0]
└── explainability: SignalExplainability
    ├── raw_value: Float                 # Unnormalized mathematical feature value
    ├── primary_driver: String           # Core feature ID driving the signal score
    ├── rationale: String                # Human-readable calculation explanation
    └── contributing_factors: Map        # Key-value weight attribution map
```

---

## 3. Comprehensive Master Field Table Specification

| Category | Signal Field Name | Sub-Entity Type | Value Range | Primary Purpose & Business Function |
| :--- | :--- | :--- | :--- | :--- |
| **Metadata** | `bundle_id` | `String` | UUID v4 | Unique identifier for this computed signal bundle. |
| **Metadata** | `message_id` | `String` | String | Foreign key matching target `MessageContext.message_id`. |
| **Metadata** | `computed_at` | `String` | ISO 8601 | UTC timestamp of signal computation completion. |
| **Metadata** | `calculation_latency_ms` | `Float` | $\ge 0.0$ | Total execution time in milliseconds taken by SignalEngine. |
| **Metadata** | `global_confidence` | `Float` | $[0.0, 1.0]$ | Overall weighted confidence across all computed signals. |
| **Metadata** | `global_completeness` | `Float` | $[0.0, 1.0]$ | Ratio of successfully computed signals vs total expected. |
| **Behaviour** | `notification_fatigue` | `SignalValue` | $[0.0, 1.0]$ | Indicates user alert overload and active notification pressure. |
| **Behaviour** | `reading_responsiveness`| `SignalValue` | $[0.0, 1.0]$ | Expected speed with which target user will read this message. |
| **Behaviour** | `reply_velocity` | `SignalValue` | $[0.0, 1.0]$ | Propensity and speed of user writing a response to sender. |
| **Behaviour** | `dismiss_propensity` | `SignalValue` | $[0.0, 1.0]$ | Likelihood of recipient swiping away alert without reading. |
| **Behaviour** | `ignore_propensity` | `SignalValue` | $[0.0, 1.0]$ | Likelihood of user leaving message unread indefinitely. |
| **Behaviour** | `time_of_day_affinity` | `SignalValue` | $[0.0, 1.0]$ | Alignment of current hour with user's active response window. |
| **Behaviour** | `weekend_responsiveness`| `SignalValue` | $[0.0, 1.0]$ | Historical propensity to engage during weekend hours. |
| **Behaviour** | `group_engagement` | `SignalValue` | $[0.0, 1.0]$ | User participation and reading activity rate in target group. |
| **Behaviour** | `business_engagement` | `SignalValue` | $[0.0, 1.0]$ | Rate of opening and replying to commercial messages. |
| **Risk** | `spam` | `SignalValue` | $[0.0, 1.0]$ | Probability of message being an unsolicited spam broadcast. |
| **Risk** | `scam` | `SignalValue` | $[0.0, 1.0]$ | Probability of malicious social engineering or scam attempt. |
| **Risk** | `fraud_indicator` | `SignalValue` | $[0.0, 1.0]$ | Financial theft, impersonation, or credential harvesting risk. |
| **Risk** | `business_trust` | `SignalValue` | $[0.0, 1.0]$ | Inverted risk rating representing business authenticity. |
| **Risk** | `forward_chain_risk` | `SignalValue` | $[0.0, 1.0]$ | Risk associated with multi-hop viral forwarded content. |
| **Risk** | `unknown_sender_risk` | `SignalValue` | $[0.0, 1.0]$ | Danger level originating from an un-saved contact number. |
| **Risk** | `visual_scam_risk` | `SignalValue` | $[0.0, 1.0]$ | Optical OCR scam risk extracted from image payloads. |
| **Risk** | `voice_scam_risk` | `SignalValue` | $[0.0, 1.0]$ | Fraud/scam indicator extracted from voice audio transcripts. |
| **Trust** | `business_trust_score` | `SignalValue` | $[0.0, 1.0]$ | Official business verification and corporate reputation score. |
| **Trust** | `relationship_score` | `SignalValue` | $[0.0, 1.0]$ | Social tie strength and mutual interaction frequency. |
| **Trust** | `known_contact_score` | `SignalValue` | $[0.0, 1.0]$ | Contact book presence, mutual contact count, and age of link. |
| **Trust** | `group_reliability` | `SignalValue` | $[0.0, 1.0]$ | Structural safety, admin verification, and history of group. |
| **Trust** | `historical_trust` | `SignalValue` | $[0.0, 1.0]$ | Multi-month safety record and lack of past spam reports. |
| **Trust** | `interaction_strength` | `SignalValue` | $[0.0, 1.0]$ | Two-way communication volume and conversation symmetry. |
| **Urgency** | `emergency` | `SignalValue` | $[0.0, 1.0]$ | High-priority safety, physical hazard, or SOS signal. |
| **Urgency** | `time_sensitive_event` | `SignalValue` | $[0.0, 1.0]$ | Event occurring within near-term time window ($< 2 \text{ hours}$). |
| **Urgency** | `payment` | `SignalValue` | $[0.0, 1.0]$ | Financial transaction, bill due, or OTP code urgency. |
| **Urgency** | `deadline` | `SignalValue` | $[0.0, 1.0]$ | Action items expiring within explicit time limit. |
| **Urgency** | `meeting` | `SignalValue` | $[0.0, 1.0]$ | Calendar invite, schedule change, or call starting soon. |
| **Urgency** | `appointment` | `SignalValue` | $[0.0, 1.0]$ | Medical, service, or personal appointment alert. |
| **Urgency** | `family_emergency` | `SignalValue` | $[0.0, 1.0]$ | Urgent assistance call from immediate family member. |
| **Urgency** | `health_emergency` | `SignalValue` | $[0.0, 1.0]$ | Medical report, hospital, or wellness critical update. |
| **Urgency** | `critical_announcement`| `SignalValue` | $[0.0, 1.0]$ | System-wide, work, or school high-priority alert. |
| **Relationship** | `tie_strength` | `SignalValue` | $[0.0, 1.0]$ | Granular graph closeness metric between sender & receiver. |
| **Relationship** | `intimacy_score` | `SignalValue` | $[0.0, 1.0]$ | Tone intimacy, casualness, and emotional closeness. |
| **Relationship** | `reciprocity_ratio` | `SignalValue` | $[0.0, 1.0]$ | Balance of incoming vs outgoing message ratio ($0.5 = \text{balanced}$). |
| **Business** | `commercial_intent` | `SignalValue` | $[0.0, 1.0]$ | Presence of sales, promotion, or service support intent. |
| **Business** | `transactional_intent` | `SignalValue` | $[0.0, 1.0]$ | Utility message (order update, shipping, receipt, OTP). |
| **Business** | `promotional_intent` | `SignalValue` | $[0.0, 1.0]$ | Marketing discount, broadcast offer, or product push. |
| **Group** | `group_importance` | `SignalValue` | $[0.0, 1.0]$ | Overall importance of group to recipient based on role/activity.|
| **Group** | `direct_mention` | `SignalValue` | $[0.0, 1.0]$ | Binary or weighted presence of @mention targeting recipient. |
| **History** | `historical_open_rate` | `SignalValue` | $[0.0, 1.0]$ | Historical fraction of sender's alerts opened by recipient. |
| **History** | `historical_reply_rate`| `SignalValue` | $[0.0, 1.0]$ | Historical fraction of sender's alerts answered by recipient. |
| **Temporal** | `quiet_hours_active` | `SignalValue` | $[0.0, 1.0]$ | Degree of overlap with recipient's scheduled quiet window. |
| **Media** | `media_importance` | `SignalValue` | $[0.0, 1.0]$ | Value density of attached image, voice transcript, or doc. |
| **Conversation**| `conversation_importance`|`SignalValue` | $[0.0, 1.0]$ | Contextual weight of ongoing active conversation thread. |

---

## 4. Signal Invariants & Quality Standards

1. **Strict Range Compliance**: $\forall s \in \text{SignalBundle}, \quad 0.0 \le s.score \le 1.0$.
2. **Confidence Bound Guarantee**: $\forall s \in \text{SignalBundle}, \quad 0.0 \le s.confidence \le 1.0$.
3. **Null-Safety Protocol**: Optional missing signals are injected with default `SignalValue` instances ($score=0.0, confidence=0.0, rationale=\text{"Default Null Object Fallback"}$).
4. **Deep Immutability**: All fields in `SignalBundle` are frozen upon instantiation. Any mutation attempt triggers an `ImmutableStateViolationException`.
