# Data Integrity Engine & Schema Validation Specification

## 1. Overview & Architectural Hierarchy

The **Data Integrity Subsystem** is composed of **`SchemaValidator`** and **`DataConsistencyEngine`**. It enforces a strict **4-Level Validation Hierarchy** to guarantee that corrupt, malformed, or orphan data records never enter the repositories or downstream context builders.

```
Raw CSV Row
    |
    v
+-------------------------------------------------------------+
| Level 1: File & Structural Validation (Delimiters, UTF-8)   |
+------------------------------+------------------------------+
                               | Pass
                               v
+-------------------------------------------------------------+
| Level 2: Field Type & Regex Format Validation               |
+------------------------------+------------------------------+
                               | Pass
                               v
+-------------------------------------------------------------+
| Level 3: Foreign Key & Referential Integrity Verification   |
+------------------------------+------------------------------+
                               | Pass
                               v
+-------------------------------------------------------------+
| Level 4: Domain & Business Rules Constraints Verification   |
+------------------------------+------------------------------+
                               | Pass
                               v
             Validated In-Memory Domain Entity
```

---

## 2. 4-Level Validation Engine Architecture

---

### Level 1: File & Structural Validation
- **Scope**: Raw file headers, row delimiters, UTF-8 character encoding, column count matching.
- **Rules**:
  - Verifies exact header string matches against system schema definitions.
  - Ensures row column counts match header count.
  - Rejects unescaped quotes or invalid line breaks.

---

### Level 2: Field Type & Format Coercion
- **Scope**: Data type parsing, value range bounds, regex syntax patterns.
- **Validation Rules**:
  - Primary Key Patterns:
    - `message_id`: Matches `^msg_\d{3}$`
    - `user_id`: Matches `^u_\d{3}$`
    - `group_id`: Matches `^group_\d{3}$`
    - `business_id`: Matches `^business_\d{3}$`
    - `image_id`: Matches `^img_\d{3}$`
    - `voice_note_id`: Matches `^voice_\d{3}$`
  - Timestamp Coercion: Must parse as valid `ISO 8601` or `YYYY-MM-DD HH:MM:SS`.
  - Non-Negative Constraints: Counters (`messages_sent_30d`, `forwarded_count`, `member_count`) must be `>= 0`.
  - Boolean Indicator Constraints: Must strictly evaluate to integer `0` or `1`.

---

### Level 3: Foreign Key & Referential Integrity Verification
- **Scope**: Cross-dataset relational dependency verification across all 13 CSVs.
- **Integrity Matrix**:

| Source Dataset | Source Column | Target Dataset | Target Column | Mandatory / Conditional Constraint |
|---|---|---|---|---|
| `messages.csv` | `user_id` | `users.csv` | `user_id` | Mandatory |
| `messages.csv` | `group_id` | `groups.csv` | `group_id` | Mandatory if `conversation_type == 'group'` |
| `messages.csv` | `business_id` | `business_accounts.csv` | `business_id` | Mandatory if `conversation_type == 'business'` |
| `messages.csv` | `sender_user_id` | `users.csv` | `user_id` | Mandatory if `conversation_type IN ('personal', 'group')` |
| `group_members.csv` | `group_id` | `groups.csv` | `group_id` | Mandatory |
| `group_members.csv` | `user_id` | `users.csv` | `user_id` | Mandatory |
| `user_business_history.csv`| `user_id` | `users.csv` | `user_id` | Mandatory |
| `user_business_history.csv`| `business_id` | `business_accounts.csv` | `business_id` | Mandatory |
| `message_history.csv` | `user_id` | `users.csv` | `user_id` | Mandatory |
| `message_events.csv` | `message_id` | `message_history.csv` | `message_id` | Mandatory |
| `daily_notification_summary.csv`| `user_id` | `users.csv` | `user_id` | Mandatory |

---

### Level 4: Domain & Business Rules Verification
- **Scope**: Logical invariants across multiple attributes.
- **Rules**:
  - `groups.csv`: `member_count >= admin_count`.
  - `messages.csv`: `media_id` MUST be populated if `media_type IN ('image', 'voice')`; MUST be NULL if `media_type` is NULL.
  - `messages.csv`: `conversation_type == 'group'` REQUIRES non-null `group_id` AND null `business_id`.
  - `messages.csv`: `conversation_type == 'business'` REQUIRES non-null `business_id` AND null `group_id` AND null `sender_user_id`.

---

## 3. Null Handling & Default Value Repair Matrix

| Attribute Scenario | Permissible Null? | Repair / Default Policy |
|---|---|---|
| Unset text payload (`message_text`) | YES | Safe conversion to Empty String `""`. |
| Missing optional timestamp (`promotions_opted_out_at`) | YES | Retained as `NULL` pointer; evaluated safely by null-coalescing check. |
| Missing junction record (`group_members.csv`) | NO | Injects synthetic default membership profile (`role = 'member'`, `muted = false`). |
| Missing business interaction history | NO | Injects default business history record (`why_user_knows = 'unknown'`, `allows_promotional = false`). |

---

## 4. Quarantine Engine & Error Recovery

### 4.1 Row Isolation & Quarantine Logging
When a raw CSV row fails Level 1 or Level 2 validation:
1. Row extraction halts for that specific record.
2. The raw row is isolated into the **`QuarantineContainer`**.
3. A detailed error entry is written to `schema_violations.log` specifying: CSV Name, Line Number, Column Name, Violation Type, Raw Value.
4. Data loading continues for remaining valid rows (non-blocking fault tolerance).

### 4.2 Critical Referential Failure Policy
If Level 3 FK validation fails for a core entity (e.g., `messages.csv` refers to non-existent `user_id`):
- In **Strict Mode**: Boot sequence aborts immediately with `FatalSchemaException`.
- In **Degraded Mode**: Row is quarantined, a default synthetic user profile is assigned, and processing proceeds with warning telemetry.
