# Decision Intelligence Data Models & Schema Contracts

## 1. Overview & Data Architecture

This document specifies the exact data schemas, field types, validation constraints, and enums for the Decision Intelligence Layer. All data structures are strictly typed and immutable after instantiation to guarantee thread safety and audit compliance.

```
+-----------------------------------------------------------------------------------------------+
|                                DECISION INTELLIGENCE OBJECT TREE                              |
|                                                                                               |
|   +---------------------------------------------------------------------------------------+   |
|   | DecisionContext                                                                       |   |
|   | ├── message_context: MessageContext                                                   |   |
|   | ├── signal_bundle: SignalBundle                                                       |   |
|   | ├── evidence_bundle: EvidenceBundle                                                   |   |
|   | ├── media_context: MediaContext (Optional)                                            |   |
|   | ├── historical_context: HistoricalContext                                             |   |
|   | ├── business_context: BusinessContext (Optional)                                      |   |
|   | └── user_context: UserContext                                                         |   |
|   +---------------------------------------------------------------------------------------+   |
|                                              │                                                |
|                                              v                                                |
|   +---------------------------------------------------------------------------------------+   |
|   | DecisionResult                                                                        |   |
|   | ├── action: DecisionAction (Enum)                                                     |   |
|   | ├── urgency_score: Float [0.0 - 1.0]                                                  |   |
|   | ├── importance_score: Float [0.0 - 1.0]                                               |   |
|   | ├── category: DecisionCategory                                                        |   |
|   | ├── reasoning_summary: String                                                         |   |
|   | ├── triggered_rule_id: String (Optional)                                              |   |
|   | ├── bypassed_llm: Boolean                                                             |   |
|   | ├── action_params: ActionParameters                                                   |   |
|   | └── metadata: DecisionMetadata                                                        |   |
|   +---------------------------------------------------------------------------------------+   |
|                                              │                                                |
|                                              v                                                |
|   +---------------------------------------------------------------------------------------+   |
|   | DecisionMetadata                                                                      |   |
|   | ├── execution_id: UUID                                                                |   |
|   | ├── latency_breakdown: LatencyBreakdown                                               |   |
|   | ├── confidence_breakdown: ConfidenceBreakdown                                         |   |
|   | ├── verification_status: VerificationStatus                                           |   |
|   | └── model_version: String                                                             |   |
|   +---------------------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Primary Action & Category Enums

### `DecisionAction` (Enum)
Defines the final routing operation executed by the client notification layer:

| Enum Key | Value | Description |
| :--- | :--- | :--- |
| `DELIVER_IMMEDIATELY` | `"DELIVER_IMMEDIATELY"` | High-priority immediate notification with sound, vibration, and banner. |
| `DELIVER_SILENT` | `"DELIVER_SILENT"` | Deliver notification to shade immediately without audio/haptic interruption. |
| `SUMMARIZE_LATER` | `"SUMMARIZE_LATER"` | Suppress banner; add to periodic notification summary roll-up. |
| `BATCH_DIGEST` | `"BATCH_DIGEST"` | Suppress banner; hold for scheduled morning/evening digest batch. |
| `SUPPRESS_SPAM` | `"SUPPRESS_SPAM"` | Silent suppression; flag as potential spam/phishing in app registry. |
| `SUPPRESS_MUTE` | `"SUPPRESS_MUTE"` | Complete silent suppression due to explicit user chat/group mute. |
| `TRIGGER_EMERGENCY_OVERRIDE` | `"TRIGGER_EMERGENCY_OVERRIDE"` | Critical override: force sound/ring tone even during Do-Not-Disturb mode. |

### `DecisionCategory` (Enum)
Categorizes the contextual domain of the notification:

| Enum Key | Description |
| :--- | :--- |
| `PERSONAL_URGENT` | High urgency personal message from close contact/family. |
| `PERSONAL_CASUAL` | Non-urgent personal chatter. |
| `WORK_CRITICAL` | Time-sensitive work communication or project alert. |
| `WORK_ROUTINE` | General work discussion or group message. |
| `TRANSACTIONAL` | Bank alert, flight status, OTP code, delivery receipt. |
| `MARKETING_PROMO` | Promotional offer, vendor deal, broadcast campaign. |
| `SAFETY_SECURITY` | Fraud alert, unauthorized login attempt, threat warning. |
| `SPAM_VIRAL` | Unsolicited broadcast, chain letter, suspicious link bundle. |

---

## 3. Schema: `DecisionContext`

The root input wrapper supplied to the Decision Engine:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DecisionContext",
  "type": "object",
  "required": [
    "context_id",
    "timestamp",
    "message_context",
    "signal_bundle",
    "evidence_bundle",
    "historical_context",
    "user_context"
  ],
  "properties": {
    "context_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier for this decision invocation frame."
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO-8601 UTC timestamp of context construction."
    },
    "message_context": {
      "$ref": "#/definitions/MessageContext",
      "description": "Extracted text payload, chat metadata, and structural features."
    },
    "signal_bundle": {
      "$ref": "#/definitions/SignalBundle",
      "description": "Aggregated numerical and categorical signals."
    },
    "evidence_bundle": {
      "$ref": "#/definitions/EvidenceBundle",
      "description": "Top retrieved grounded context snippets."
    },
    "media_context": {
      "type": ["object", "null"],
      "description": "Multimodal analysis metadata (image/voice context if present)."
    },
    "historical_context": {
      "type": "object",
      "description": "Recent 7-day interaction velocity, missed calls, response patterns."
    },
    "business_context": {
      "type": ["object", "null"],
      "description": "Verified business metadata, campaign IDs, transactional tags."
    },
    "user_context": {
      "type": "object",
      "description": "User current active status, quiet hours rules, address book status."
    }
  }
}
```

---

## 4. Schema: `DecisionResult`

The final validated output payload returned by the Decision Engine:

| Field Name | Type | Allowed Values / Range | Nullable | Description |
| :--- | :--- | :--- | :--- | :--- |
| `decision_id` | String (UUID) | Valid UUID v4 | NO | Unique execution ID for tracing. |
| `context_id` | String (UUID) | Valid UUID v4 | NO | References corresponding `DecisionContext.context_id`. |
| `action` | String (Enum) | `DecisionAction` values | NO | Final notification routing action. |
| `urgency_score` | Float | `0.0` to `1.0` | NO | Calibrated message urgency level. |
| `importance_score` | Float | `0.0` to `1.0` | NO | Calibrated message importance level. |
| `category` | String (Enum) | `DecisionCategory` values | NO | Primary message domain classification. |
| `reasoning_summary` | String | Max 250 chars | NO | Structured natural language explanation. |
| `triggered_rule_id` | String | Rule ID string | YES | Rule ID if deterministic rule fired; `null` if LLM used. |
| `bypassed_llm` | Boolean | `true`, `false` | NO | `true` if Rule Engine short-circuited LLM. |
| `action_params` | Object | `ActionParameters` struct | NO | Client presentation instructions (sound, vibration, banner). |
| `metadata` | Object | `DecisionMetadata` struct | NO | Latency, confidence breakdown, audit hashes. |

---

## 5. Schema: `DecisionMetadata`

Contains telemetry, calibration metrics, latency tracing, and verification flags:

```json
{
  "type": "object",
  "required": [
    "execution_id",
    "model_version",
    "latency_breakdown",
    "confidence_breakdown",
    "verification_status",
    "audit_hash"
  ],
  "properties": {
    "execution_id": { "type": "string", "format": "uuid" },
    "model_version": { "type": "string", "example": "llm-router-v2.4.1" },
    "latency_breakdown": {
      "type": "object",
      "properties": {
        "preprocessing_ms": { "type": "number" },
        "rule_engine_ms": { "type": "number" },
        "llm_reasoner_ms": { "type": "number" },
        "confidence_calc_ms": { "type": "number" },
        "validation_ms": { "type": "number" },
        "total_latency_ms": { "type": "number" }
      }
    },
    "confidence_breakdown": {
      "type": "object",
      "properties": {
        "raw_llm_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "signal_agreement_factor": { "type": "number" },
        "evidence_relevance_factor": { "type": "number" },
        "calibrated_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
      }
    },
    "verification_status": {
      "type": "object",
      "properties": {
        "schema_valid": { "type": "boolean" },
        "grounding_verified": { "type": "boolean" },
        "consistency_verified": { "type": "boolean" },
        "fallback_applied": { "type": "boolean" }
      }
    },
    "audit_hash": { "type": "string", "description": "SHA-256 hash of context + result for tamper-proof logging." }
  }
}
```

---

## 6. Supporting Data Objects

### `ActionParameters`
Defines device notification execution properties:
* `play_sound` (Boolean): Enable alert ringtone/chime.
* `vibrate` (Boolean): Enable haptic pattern.
* `banner_style` (String): `HEADS_UP`, `SILENT_SHADE`, `SUMMARY_CARD`, `NONE`.
* `scheduled_time` (String, Optional): ISO-8601 timestamp if action is `BATCH_DIGEST` or `SUMMARIZE_LATER`.

### `RuleEvaluationResult`
* `rule_fired` (Boolean): Indicates whether a deterministic rule matched.
* `rule_id` (String, Optional): Identifier of the fired rule.
* `action` (DecisionAction, Optional): Action assigned by rule.
* `priority` (Integer): Priority level (80 - 100).
* `bypass_llm` (Boolean): True if rule short-circuits LLM evaluation.

### `VerificationResult`
* `is_valid` (Boolean): True if decision passed all validation gates.
* `validation_errors` (Array of Strings): List of specific validation failure descriptions.
* `suggested_fallback_action` (DecisionAction, Optional): Safe fallback action if invalid.
