# Standardized Master MessageContext Blueprint

## 1. Executive Summary & Object Design Principles

The `MessageContext` object is the unified, immutable, and fully enriched master data contract produced by the Context Assembly Engine for every incoming WhatsApp message.

### Schema Design Guarantees
1. **Single Point of Truth**: Contains all structural, entity, relationship, historical, behavioral, and multimodal context required by any downstream module.
2. **Zero Null Errors**: All fields are strictly typed. Missing optional sub-entities are populated with deterministic, non-null Default Sub-Context Objects (Null Object Pattern).
3. **Immutability**: Freezes all nested sub-objects upon completion of assembly and validation.
4. **Auditability**: Embedded assembly metadata and quality scores track exact data origin, timing, and structural completeness.

---

## 2. Master `MessageContext` Root Schema Overview

```
MessageContext (Master Container)
│
├── context_metadata: ContextMetadata
├── core_message: CoreMessageContext
├── temporal_info: TemporalInformation
├── sender: UserContext
├── receiver: UserContext
├── conversation: ConversationContext
├── group: GroupContext
├── business: BusinessContext
├── media: MediaContext
├── history: HistoryContext
├── notification_behaviour: NotificationContext
├── relationship: RelationshipContext
├── behaviour_stats: BehaviourContext
└── quality_metrics: ContextQualityMetrics
```

---

## 3. Comprehensive Master Field Table Specification

| Field Category | Field Name | Data Type | Source Data | Nullable | Field Purpose & Business Justification | Future Consumers |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **Assembly Metadata** | `context_id` | `String` | UUID v4 Generator | No | System-wide unique identifier for this context assembly instance. | Audit Logger, Tracing Engine |
| **Assembly Metadata** | `assembled_at` | `String` | System Clock (ISO 8601) | No | Exact millisecond timestamp when context assembly completed. | Latency Monitor, Metric Aggregator |
| **Assembly Metadata** | `assembly_latency_ms` | `Float` | Execution Timer | No | End-to-end processing time in milliseconds taken by Context Assembly Engine. | System Performance Monitor |
| **Assembly Metadata** | `completeness_score` | `Float` | Quality Engine | No | Global normalized context richness score ($0.0 \le Q \le 1.0$). | Quality Analyzer, Downstream AI |
| **Core Message** | `message_id` | `String` | `messages.csv` (`message_id`) | No | Unique message primary key. | All Downstream Modules |
| **Core Message** | `raw_text_content` | `String` | `messages.csv` (`content`) | No | Exact textual body of the incoming message. | Content Analyzers, Summarizers |
| **Core Message** | `cleaned_text` | `String` | Data Normalizer | No | Sanitized, whitespace-normalized, and control-character-stripped text. | Text Processing Components |
| **Core Message** | `message_type` | `String (Enum)` | `messages.csv` (`message_type`) | No | Type code: `"TEXT"`, `"IMAGE"`, `"VOICE"`, `"DOCUMENT"`, `"VIDEO"`, `"LOCATION"`. | Multimodal Parsers, Classifiers |
| **Core Message** | `char_count` | `Int` | Computed | No | Length of raw text in characters. | Priority Estimators, Stats Engine |
| **Core Message** | `word_count` | `Int` | Computed | No | Total word count of the message payload. | Read Time Estimators |
| **Core Message** | `contains_links` | `Boolean` | Regex Matcher | No | Indicates presence of HTTP/HTTPS URLs in message content. | Security Engine, Link Parsers |
| **Core Message** | `contains_phone_numbers`| `Boolean` | Regex Matcher | No | Indicates presence of contact phone numbers in text. | Safety Engine, Spam Detectors |
| **Forwarding Info** | `is_forwarded` | `Boolean` | `messages.csv` (`is_forwarded`) | No | Indicates if message was forwarded from another chat. | Authenticity Scorer, Spam Detector |
| **Forwarding Info** | `forward_count` | `Int` | `messages.csv` (`forward_count`) | No | Number of times message has been re-forwarded across network. | Virality Analyzer, Risk Engine |
| **Forwarding Info** | `is_frequently_forwarded`| `Boolean` | Computed (`forward_count >= 5`)| No | Flag for highly broadcasted viral content. | Risk Engine, Scam Filter |
| **Temporal Info** | `timestamp_epoch_ms` | `Int` | `messages.csv` (`timestamp`) | No | UTC epoch timestamp of message transmission. | Time Series Analyzer, Sequencer |
| **Temporal Info** | `iso_timestamp` | `String` | Computed (ISO 8601) | No | Human-readable ISO UTC string (`YYYY-MM-DDTHH:MM:SSZ`). | Logging Systems, UI Components |
| **Temporal Info** | `day_of_week` | `String` | Computed | No | Day of transmission (`"MONDAY"` to `"SUNDAY"`). | Behavioral Model, Pattern Analyzer |
| **Temporal Info** | `hour_of_day` | `Int` | Computed ($0 \le h \le 23$) | No | Hour of message transmission in local target user timezone. | Quiet Hours Analyzer |
| **Temporal Info** | `is_weekend` | `Boolean` | Computed | No | Flag indicating weekend transmission (`SATURDAY` / `SUNDAY`). | Availability Estimator |
| **Temporal Info** | `is_working_hours` | `Boolean` | Computed | No | Flag indicating transmission during standard business hours (09:00 - 17:00).| Schedule Analyzer |
| **Sender Context** | `sender` | `UserContext` | `users.csv` + Lookups | No | Full structured user object for the sender. Reused standard model. | All Modules |
| **Receiver Context** | `receiver` | `UserContext` | `users.csv` + Lookups | No | Full structured user object for the recipient. Reused standard model. | All Modules |
| **Conversation** | `conversation` | `ConversationContext` | Lookups + Stats | No | Aggregated context regarding thread activity, dynamics, and cadence. | Thread Analyzers |
| **Group Context** | `group` | `GroupContext` | `groups.csv` + `group_members.csv` | No | Full group workspace, hierarchy, role, and activity details (Default object if DM).| Group Analyzers |
| **Business Context** | `business` | `BusinessContext` | `business_accounts.csv` | No | Commercial account verification, category, and support metadata (Default if non-business).| Commercial Entity Parsers |
| **Media Context** | `media` | `MediaContext` | Multimodal Layer Cache | No | Rich OCR text, table structures, voice transcripts, acoustic tone, visual objects. | Multimodal Summarizers |
| **History Context** | `history` | `HistoryContext` | `message_history.csv` + `message_events.csv` | No | Recent thread events, past interactions, and historical message context. | Temporal Pattern Analyzers |
| **Notification Context**| `notification_behaviour`| `NotificationContext` | `daily_notification_summary.csv` | No | Sender/Receiver historical delivery rates, open rates, response latencies. | Volume Estimators |
| **Relationship** | `relationship` | `RelationshipContext` | `user_business_history.csv` + Joins | No | Relational attributes: sender-receiver pair, user-group role, user-business tie. | Relational Affinity Scorer |
| **Behaviour Stats** | `behaviour_stats` | `BehaviourContext` | Computed Aggregates | No | Statistical behavioral profiles for sender and receiver interaction habits. | Behavioral Profilers |
| **Quality Metrics** | `quality_metrics` | `ContextQualityMetrics`| Context Quality Engine | No | Validation flags, completeness score breakdown, and field missingness indicators. | System Monitors, Safety Audits |

---

## 4. Sub-Context Access & Invariant Guarantees

### Invariant Rules
1. **Non-Null Property Guarantees**: Under no circumstance will accessing `message_context.sender`, `message_context.group`, or `message_context.media` throw a `NullPointerException` or return `None`.
2. **Type Disambiguation via Flags**:
   - `message_context.conversation.is_group_chat` disambiguates DM vs Group conversations.
   - `message_context.business.is_business_account` disambiguates Peer-to-Peer vs Business interactions.
   - `message_context.media.has_media` disambiguates Text-Only vs Multimodal messages.
3. **Strict Deep Immutability**: All list and map properties within `MessageContext` are wrapped in unmodifiable/frozen read-only data structures. Modifying any field after creation raises an `ImmutableStateViolationException`.
