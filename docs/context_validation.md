# Context Validation, Null Handling & Fallback Architecture

## 1. Validation Philosophy & Design Goals

The `ContextValidationService` ensures that no incomplete, corrupted, or structurally invalid context object is ever emitted to downstream AI modules.

### Core Validation Directives
1. **Zero Unhandled Nulls**: Never expose explicit `null` / `None` references for missing sub-contexts or optional fields.
2. **Deterministic Fallbacks**: Substitute missing or unresolvable entities with standardized Default Sub-Context Objects (Null Object Pattern).
3. **Graceful Degradation**: Downgrade context completeness scores rather than failing when secondary data sources (e.g., historical logs, notification summaries) are absent.
4. **Strict Boundary Validation**: Enforce boundary conditions on numerical metrics (scores bounded between $0.0$ and $1.0$).

---

## 2. Validation Pipeline Architecture

The validation pipeline consists of 4 sequential verification filters applied to the `UnvalidatedContextBag` before object construction.

```
UnvalidatedContextBag
       │
       ▼
┌───────────────────────────────────────────────────────────┐
│ Stage 1: Structural & Schema Validation                   │
│ (Checks mandatory fields, string non-emptiness, types)    │
└──────────────────────────────┬────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────┐
│ Stage 2: Referential Integrity & Link Checks              │
│ (Verifies sender-receiver-group ID relationships)        │
└──────────────────────────────┬────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────┐
│ Stage 3: Boundary & Value Normalization                   │
│ (Clamps scores between 0.0 and 1.0, validates timestamps)  │
└──────────────────────────────┬────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────┐
│ Stage 4: Completeness Scoring & Fallback Injection        │
│ (Calculates Q-score, injects Default Objects for missing) │
└──────────────────────────────┬────────────────────────────┘
                               │
                               ▼
Validated & Sealed MessageContext
```

---

## 3. Handling Edge Cases & Data Anomalies

### 1. Missing Data Handling
- **Missing CSV Records**: When a user or business ID in a raw message does not exist in `users.csv` or `business_accounts.csv`, the engine flags `is_registered_user = False` or `is_business_account = False` and hydrates default fallback profiles.
- **Empty Message Body**: When raw text is empty (e.g., media-only transmission), `cleaned_text` is set to `""` and `word_count` to `0` without triggering validation errors.

### 2. Broken Relationship Recovery
- **Orphan Group Memberships**: If `group_members.csv` contains a record for a user in a group that does not exist in `groups.csv`, the group builder degrades to `DEFAULT_GROUP_CONTEXT` with a `BROKEN_GROUP_RELATIONSHIP` warning flag.
- **Dangling Business History**: If `user_business_history.csv` references a deleted or non-existent `business_id`, the relationship builder falls back to `PEER_TO_PEER` classification.

### 3. Missing Media Handling
- **Missing Media Cache Payload**: If a message has `message_type = "IMAGE"` or `"VOICE"` but the asset is absent or corrupted in `IMultimodalCache`, the media builder returns `FAILED_MEDIA_CONTEXT` with `validation_status = "CORRUPTED"`, `has_media = True`, and zero-valued scores.

---

## 4. Standardized Default Sub-Context Objects (Null Object Pattern)

To guarantee type safety across downstream consumers, the engine pre-defines standardized immutable default objects:

### `DEFAULT_USER_CONTEXT`
```yaml
user_id: "UNKNOWN_USER"
display_name: "Unknown Contact"
phone_number: "UNKNOWN"
user_type: "INDIVIDUAL"
registration_timestamp: 0
account_age_days: 0
preferred_language: "en"
timezone: "UTC"
is_verified: false
is_registered_user: false
```

### `DEFAULT_GROUP_CONTEXT`
```yaml
group_id: "NONE"
group_name: "Direct Message"
group_type: "DIRECT_CHAT"
created_at_timestamp: 0
total_member_count: 2
is_announcement_only: false
sender_role: "NON_MEMBER"
sender_joined_at: 0
sender_is_muted_in_group: false
```

### `DEFAULT_BUSINESS_CONTEXT`
```yaml
business_id: "NONE"
business_name: "Non-Business"
category: "NON_BUSINESS"
verification_status: "UNVERIFIED"
support_email: ""
catalog_enabled: false
expected_sla_minutes: 0
is_business_account: false
```

### `DEFAULT_MEDIA_CONTEXT`
```yaml
media_id: "NONE"
media_type: "TEXT_ONLY"
sha256_hash: ""
has_media: false
image_summary: ""
image_category: "NONE"
ocr_extracted_text: ""
image_risk_score: 0.0
voice_transcript: ""
voice_duration_seconds: 0.0
acoustic_tone: "NEUTRAL"
voice_urgency_score: 0.0
```

---

## 5. Complete Validation Rules Matrix

| Component | Check Target | Validation Condition | Violation Action | Fallback Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Core Message** | `message_id` | Must be non-empty string | Reject Payload | Raise `InvalidPayloadException` |
| **Core Message** | `timestamp` | $0 < t \le \text{Current System Time}$ | Clamp Timestamp | Use current system epoch ms |
| **User Context** | `user_id` | Must match UUID pattern | Flag Warning | Substitute `DEFAULT_USER_CONTEXT` |
| **User Context** | `timezone` | Must be valid IANA timezone | Log Warning | Fallback to `"UTC"` |
| **Group Context** | `sender_role` | Must be `"ADMIN"`, `"MEMBER"`, `"NON_MEMBER"` | Reset Role | Set to `"NON_MEMBER"` |
| **Media Context** | Scores | $0.0 \le \text{score} \le 1.0$ | Clamp Value | Clamp values to $[0.0, 1.0]$ bounds |
| **History** | `last_interaction` | $\le \text{Current Message Timestamp}$ | Fix Inconsistency| Set `days_since_last_interaction = 0.0` |
