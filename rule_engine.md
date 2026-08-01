# Deterministic Rule Engine & Hard Safety Overrides Specification

## 1. Deterministic Rule Engine Architecture

The **Rule Engine** provides a ultra-low-latency, zero-shot, deterministic decision evaluation system for incoming WhatsApp notifications. It operates ahead of any AI or LLM processing, executing hard user rules, safety overrides, and explicit system constraints in less than 5 milliseconds.

```
+-----------------------------------------------------------------------------------------------+
|                                      RULE ENGINE PIPELINE                                     |
|                                                                                               |
|   DecisionContext                                                                             |
|          |                                                                                    |
|          v                                                                                    |
|   +---------------------------------------------------------------------------------------+   |
|   | Rule Evaluator (Registry Iterator)                                                    |   |
|   | - Sorts registered rules by precedence (100 -> 80)                                    |   |
|   | - Sequentially evaluates match conditions against DecisionContext                     |   |
|   +---------------------------------------------------------------------------------------+   |
|          |                                                                                    |
|          +-----------------------+-----------------------+                                    |
|          |                       |                       |                                    |
|          v                       v                       v                                    |
|   [Level 0 Rules]         [Level 1 Rules]         [No Rule Fired]                             |
|   - Safety Overrides      - Quiet Hours           - Pass context to LLM Reasoner              |
|   - Hard Security         - Muted Groups          - bypass_llm = FALSE                        |
|   - Instant Block         - VIP Overrides                                                     |
|          |                       |                                                            |
|          v                       v                                                            |
|   RuleMatchResult         RuleMatchResult                                                     |
|   - bypass_llm = TRUE     - bypass_llm = TRUE                                                 |
|   - confidence = 1.0      - confidence = 0.95-1.0                                             |
|          |                       |                                                            |
|          +-----------------------+                                                            |
|          |                                                                                    |
|          v                                                                                    |
|   Short-Circuit Output -> Jump to ConfidenceEngine & OutputValidator                          |
+-----------------------------------------------------------------------------------------------+
```

### Key Architectural Characteristics
1. **Zero LLM Dependency**: Evaluates pure boolean logic and numerical thresholds without network roundtrips to LLMs.
2. **Short-Circuit Mechanics**: Immediately halts rule iteration upon encountering the first matching high-priority rule (Level 0 or Level 1).
3. **Immutability & Safety**: Rule evaluation cannot mutate `DecisionContext` or persistent system state.

---

## 2. LLM Bypass Matrix

Decisions that match specific deterministic patterns **MUST** bypass the LLM Reasoner entirely. Bypassing the LLM guarantees instant delivery (<5ms), zero LLM token costs, absolute predictability, and deterministic safety compliance.

| Rule Category | Trigger Condition | Decision Action | Priority | Latency Saved | Safety & Business Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Critical Safety** | Verified self-harm or violent threat signal | `TRIGGER_EMERGENCY_OVERRIDE` | 100 | ~300 ms | Immediate emergency routing; zero probabilistic error tolerance. |
| **Security 2FA / OTP** | Verified 2FA verification code / OTP payload | `DELIVER_IMMEDIATELY` | 100 | ~300 ms | Users require instantaneous OTP notification to complete logins. |
| **Explicit Mute (Chat/Group)** | Chat ID in user `muted_chats_list` and NO direct mention | `SUPPRESS_MUTE` | 95 | ~300 ms | Explicit user settings must never be overridden by AI guesses. |
| **Known Spam Blacklist** | Sender ID in global spam blacklist OR spam score > 0.95 | `SUPPRESS_SPAM` | 95 | ~300 ms | Saves cost and prevents malicious content exposure. |
| **Hard Quiet Hours (Standard)**| Time in quiet window AND sender NOT in VIP list AND urgency < 0.9 | `DELIVER_SILENT` | 90 | ~300 ms | Enforces user sleep/work preferences reliably. |
| **VIP Quiet Hour Bypass** | Time in quiet window AND sender in VIP list AND urgency >= 0.8 | `DELIVER_IMMEDIATELY` | 90 | ~300 ms | Guaranteed family/emergency contact reachability. |
| **Repeated Forwarded Viral** | `is_forwarded` == True AND `forward_count` >= 5 AND unknown sender | `BATCH_DIGEST` | 85 | ~300 ms | Suppresses chain messages and viral spam noise. |
| **Transactional Receipt** | Verified business badge AND `transactional_type` in [RECEIPT, SHIPMENT] | `DELIVER_SILENT` | 80 | ~300 ms | Timely record keeping without intrusive audio interruption. |

---

## 3. Comprehensive Rule Catalog & Logic Specifications

### 3.1. Safety Overrides (Level 0 - Priority 100)
* **Threat & Harassment Filter**:
  * *Condition*: `SignalBundle.safety_risk_score > 0.85` OR `MessageContext.has_harassment_flag == True`
  * *Action*: `SUPPRESS_SPAM` with safety warning meta-flag.
  * *Bypass LLM*: `TRUE`
* **OTP / 2FA Security Bypass**:
  * *Condition*: `MessageContext.is_otp_code == True` AND `SignalBundle.trust_score > 0.8`
  * *Action*: `DELIVER_IMMEDIATELY` (High priority banner, sound enabled).
  * *Bypass LLM*: `TRUE`

### 3.2. Spam & Scam Rules (Level 0 / Level 1 - Priority 95)
* **Unsolicited Broadcast Pattern**:
  * *Condition*: Sender not in address book AND `MessageContext.is_broadcast == True` AND `SignalBundle.spam_probability > 0.70`
  * *Action*: `SUPPRESS_SPAM`
  * *Bypass LLM*: `TRUE`
* **Phishing Link & High Link Density**:
  * *Condition*: Sender not in address book AND `MessageContext.link_count >= 2` AND `SignalBundle.phishing_risk_score > 0.75`
  * *Action*: `SUPPRESS_SPAM`
  * *Bypass LLM*: `TRUE`
* **Impersonation & Financial Request**:
  * *Condition*: Sender claims identity of known contact but phone number differs AND text requests money/UPI transfer
  * *Action*: `SUPPRESS_SPAM` (Triggers visual security warning alert)
  * *Bypass LLM*: `TRUE`

### 3.3. Quiet Hours & User State Rules (Level 1 - Priority 90)
* **Strict Quiet Window (Non-VIP)**:
  * *Condition*: `UserContext.is_quiet_hours_active == True` AND `UserContext.sender_is_vip == False` AND `SignalBundle.urgency_score < 0.85`
  * *Action*: `DELIVER_SILENT`
  * *Bypass LLM*: `TRUE`
* **VIP Contact Emergency Override**:
  * *Condition*: `UserContext.is_quiet_hours_active == True` AND `UserContext.sender_is_vip == True` AND (`SignalBundle.urgency_score >= 0.75` OR `MessageContext.is_repeated_call_attempt == True`)
  * *Action*: `DELIVER_IMMEDIATELY`
  * *Bypass LLM*: `TRUE`

### 3.4. Muted Groups & Channel Rules (Level 1 - Priority 95)
* **Explicit Group Mute (No Mention)**:
  * *Condition*: `MessageContext.is_group == True` AND `UserContext.chat_is_muted == True` AND `MessageContext.user_is_mentioned == False`
  * *Action*: `SUPPRESS_MUTE`
  * *Bypass LLM*: `TRUE`
* **Explicit Group Mute (Direct Mention Exception)**:
  * *Condition*: `MessageContext.is_group == True` AND `UserContext.chat_is_muted == True` AND `MessageContext.user_is_mentioned == True`
  * *Action*: Evaluate via LLM Reasoner (Bypass LLM = `FALSE`, Priority 75)

### 3.5. Business & Transactional Rules (Level 1 - Priority 80 - 85)
* **Verified Business Transactional**:
  * *Condition*: `BusinessContext.is_verified_business == True` AND `BusinessContext.message_category == TRANSACTIONAL`
  * *Action*: `DELIVER_SILENT`
  * *Bypass LLM*: `TRUE`
* **Unverified Business Marketing / Promotional**:
  * *Condition*: `BusinessContext.is_verified_business == False` AND `BusinessContext.message_category == PROMOTIONAL`
  * *Action*: `BATCH_DIGEST`
  * *Bypass LLM*: `TRUE`

### 3.6. Known Contacts & Relationship Rules (Level 1 - Priority 80)
* **Direct VIP One-on-One Message**:
  * *Condition*: `MessageContext.is_group == False` AND `UserContext.sender_is_vip == True` AND `UserContext.is_quiet_hours_active == False`
  * *Action*: `DELIVER_IMMEDIATELY`
  * *Bypass LLM*: `TRUE`
* **Direct Address Book Contact**:
  * *Condition*: `MessageContext.is_group == False` AND `UserContext.sender_in_address_book == True` AND `UserContext.is_quiet_hours_active == False`
  * *Action*: Evaluate via LLM Reasoner for optimal presentation (Bypass LLM = `FALSE`)

### 3.7. Emergency & Urgent Escalation Rules (Level 0 - Priority 100)
* **Explicit Emergency Keyword Signal**:
  * *Condition*: `SignalBundle.emergency_keyword_detected == True` AND `UserContext.sender_in_address_book == True`
  * *Action*: `TRIGGER_EMERGENCY_OVERRIDE`
  * *Bypass LLM*: `TRUE`
* **Repeated Call / Urgent Outreach**:
  * *Condition*: `HistoricalContext.recent_missed_calls_from_sender >= 2` within 10 minutes
  * *Action*: `TRIGGER_EMERGENCY_OVERRIDE`
  * *Bypass LLM*: `TRUE`

### 3.8. Repeated Promotional & Forwarded Message Rules (Level 1 - Priority 85)
* **Repeated Vendor Promotions**:
  * *Condition*: `BusinessContext.promotional_count_24h > 3`
  * *Action*: `SUPPRESS_SPAM`
  * *Bypass LLM*: `TRUE`
* **Chain / Viral Forwarded Message**:
  * *Condition*: `MessageContext.is_forwarded_many_times == True` AND `UserContext.sender_is_vip == False`
  * *Action*: `BATCH_DIGEST`
  * *Bypass LLM*: `TRUE`

### 3.9. Payment & Financial Reminder Rules (Level 1 - Priority 85)
* **Impending Bill Due Date (<24h)**:
  * *Condition*: `BusinessContext.is_payment_reminder == True` AND `BusinessContext.hours_until_due <= 24`
  * *Action*: `DELIVER_IMMEDIATELY`
  * *Bypass LLM*: `TRUE`

### 3.10. Critical System & Schedule Announcements (Level 1 - Priority 90)
* **Flight / Train Schedule Alert**:
  * *Condition*: `BusinessContext.is_travel_alert == True` AND `SignalBundle.urgency_score > 0.70`
  * *Action*: `DELIVER_IMMEDIATELY`
  * *Bypass LLM*: `TRUE`

---

## 4. Rule Precedence, Short-Circuiting & Evaluation Flow

Rules are registered into an indexed priority array. Evaluation iterates sequentially:

```
Sort Registered Rules by (Priority DESC, RuleID ASC)
  │
  ├─ Rule 1 (Priority 100 - Threat Detection) ──> Match? ──YES──> Return Match (Bypass LLM)
  │                                                  │
  │                                                  NO
  │                                                  │
  ├─ Rule 2 (Priority 100 - OTP Code) ─────────> Match? ──YES──> Return Match (Bypass LLM)
  │                                                  │
  │                                                  NO
  │                                                  │
  ├─ Rule 3 (Priority 95 - Explicit Group Mute)──> Match? ──YES──> Return Match (Bypass LLM)
  │                                                  │
  │                                                  NO
  │                                                  │
  ...
  │
  └─ End of Deterministic Registry ────────────> No Match ────> Set bypass_llm = FALSE
                                                                 Pass to DecisionOrchestrator
```

### Execution Guarantee
If any deterministic rule matches, `RuleEngine` returns a `RuleEvaluationResult` containing:
* `rule_fired`: True
* `rule_id`: String (e.g., `RULE_OTP_BYPASS_001`)
* `action`: Action Enum
* `priority`: Integer
* `bypass_llm`: True
* `confidence`: 1.0 (or 0.95 for soft rules)
