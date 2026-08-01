# Message Notification Router — Implementation & Execution Plan

> **Hackathon:** WhatsApp Message Notification Router  
> **Team:** VibeSync (Vishal & Sneha)  
> **Objective:** Build an AI-powered system that classifies every incoming WhatsApp message into `notify`, `digest`, or `mute` using personalization, multimodal understanding, business context, historical behavior, and risk-awareness.

---

## Overall System Architecture (High-Level)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                                  │
│  messages.csv  +  12 context CSVs  +  media/ (images & audio)      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PREPROCESSING ENGINE                            │
│  • CSV loader & joiner       • Text normalizer                      │
│  • Image → caption (OCR/VLM) • Voice → transcript (Whisper/ASR)    │
│  • Feature extraction        • Context assembler                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SIGNAL COMPUTATION LAYER                          │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │ User Profile│ │ Group Context│ │Biz Reputation│ │Risk Scorer │ │
│  │  Signals    │ │   Signals    │ │   Signals    │ │ (spam/scam)│ │
│  └─────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐                 │
│  │  History &  │ │  Urgency &   │ │  Fatigue &   │                 │
│  │  Evidence   │ │  Relevance   │ │  Repetition  │                 │
│  └─────────────┘ └──────────────┘ └──────────────┘                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ROUTING DECISION ENGINE                        │
│  • Rule-based hard filters (safety override)                        │
│  • LLM-based contextual reasoner (Claude / GPT-4o)                 │
│  • Confidence calibrator                                            │
│  • Evidence retriever (historical message IDs)                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                │
│  output.csv: message_id | action | message_type | reason |          │
│              confidence | evidence_message_ids                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow (Step-by-Step)

1. **Load** `messages.csv` (110 rows to predict) → primary input loop.
2. For each `message_id`, **join** contextual tables using foreign keys:
   - `user_id` → `users.csv`, `message_history.csv`, `message_events.csv`, `daily_notification_summary.csv`
   - `group_id` → `groups.csv`, `group_members.csv`
   - `business_id` → `business_accounts.csv`, `user_business_history.csv`
   - `media_id` → `images.csv` or `voice_notes.csv` → `media/`
3. **Multimodal extraction**: if image → run OCR + VLM caption; if voice → run ASR transcription.
4. **Compute signal scores** across 7 signal modules (see Phase 3).
5. **Hard filter check**: if scam/spam signals fire → immediately route `mute` (bypass LLM).
6. **LLM reasoning pass**: assemble rich context prompt → call LLM → parse `action`, `message_type`, `reason`, `confidence`, `evidence_message_ids`.
7. **Calibrate** confidence, validate format, write to `output.csv`.

---

## Technology Stack & Tools

| Layer | Technology | Why |
|---|---|---|
| Data loading | Python `pandas` | Fast CSV joins across 13 files |
| Image analysis | `pytesseract` (OCR) + `GPT-4o` or `Claude claude-sonnet-4-6` vision | Poster/screenshot understanding |
| Voice transcription | `openai-whisper` (local) or Whisper API | Low latency, offline-capable |
| Text embedding | `sentence-transformers` (all-MiniLM-L6-v2) | History similarity search |
| History retrieval | FAISS or BM25 (`rank_bm25`) | Fast evidence_message_ids lookup |
| LLM reasoning | Claude claude-sonnet-4-6 (primary), GPT-4o (fallback) | Best contextual reasoning, cost-efficient |
| Batching | Python `asyncio` + `httpx` | Parallel API calls for 110 messages |
| Output | `pandas` to CSV | Exact format compliance |
| Logging | Python `logging` + JSONL | Full audit trail |

---

## Phase-wise Implementation Plan

---

### Phase 0 — Environment Setup & Data Audit

**Objective:** Set up a clean working environment, load all 13 files, understand data shapes, and validate quality before building anything.

**Duration:** 1–2 hours

**Key Tasks:**
- Install all dependencies (`pandas`, `sentence-transformers`, `faiss-cpu`, `rank_bm25`, `openai-whisper`, `pytesseract`, `anthropic`, `asyncio`, `httpx`)
- Load all 13 CSVs; print shapes, null counts, unique IDs
- Validate that every `message_id` in `output.csv` exists in `messages.csv`
- Check `media_id` references against `images.csv` and `voice_notes.csv`
- Load `sample_messages.csv` to understand the expected output style/vocabulary for `reason` and `message_type`
- Build a master lookup dictionary: `{message_id: {all_context_fields}}`

**Inputs:** All 13 CSVs + `media/` folder  
**Outputs:** Master context dictionary, data audit report  

**Architecture/Design:** Single-pass data audit script. Nothing is computed here — only loaded, inspected, and indexed.

**Risks:**
- Mismatched foreign keys (e.g., `group_id` present in message but missing in `groups.csv`) → handle with `.get()` with defaults
- Some `media_id` may be null → graceful null checks before file reads

**Dependencies:** None (first phase)

---

### Phase 1 — Multimodal Preprocessing

**Objective:** Extract meaningful text and semantic content from images and voice notes so they can be reasoned over like text messages.

**Duration:** 2–3 hours

**Key Tasks:**

**Images:**
- For each `media_id` of type image, load the file from `media/`
- Run OCR (`pytesseract`) to extract any embedded text (important for posters, screenshots of scams)
- Run a VLM (Claude claude-sonnet-4-6 vision or GPT-4o) with the prompt: *"Describe this image in 1–2 sentences. Is it a promotional poster, screenshot, scam notice, personal photo, or something else?"*
- Store: `{media_id: {ocr_text, vlm_caption, media_category}}`

**Voice Notes:**
- For each `media_id` of type voice, load audio from `media/`
- Run Whisper (`whisper.transcribe(path)`) to get transcript
- Store: `{media_id: {transcript, duration_seconds}}`

**Components:**
- `MediaProcessor` class with `process_image(path)` and `process_audio(path)` methods
- Caching layer: save results to `media_cache.json` so re-runs don't re-process

**Inputs:** `images.csv`, `voice_notes.csv`, `media/` folder  
**Outputs:** `media_cache.json` — enriched media metadata  

**Architecture/Design:** Lazy evaluation — only process media when `media_id` is not null. Batch image calls to VLM (10 at a time) to reduce latency and cost.

**Risks:**
- Whisper may be slow locally for many files → batch or use API version
- VLM API costs → cache aggressively; do not re-process same `media_id` twice

**Tools:** `openai-whisper`, `pytesseract`, `Pillow`, `anthropic` (vision), `json`

**Evaluation / Success Criteria:** Every non-null `media_id` has an entry in `media_cache.json` with at least one non-empty field (`ocr_text` OR `vlm_caption` OR `transcript`).

---

### Phase 2 — Context Assembly

**Objective:** For each message, assemble a unified, richly structured context object that the routing engine can reason over — combining message fields, user profile, group info, business data, and media output.

**Duration:** 2 hours

**Key Tasks:**
- Build `ContextAssembler` that takes a `message_id` and returns a fully populated `MessageContext` dict
- Join fields from all 13 sources:

```python
MessageContext = {
  # Core message
  "message_id": ...,
  "user_id": ...,
  "conversation_type": ...,  # personal | group | business
  "message_text": ...,
  "media_type": ...,
  "forwarded_count": ...,
  "created_at": ...,

  # User profile
  "user_quiet_hours": ...,
  "user_notification_load_today": ...,
  "user_reply_rate": ...,
  "user_open_rate": ...,
  "user_mute_behavior": ...,

  # Group context (if group)
  "group_type": ...,
  "group_size": ...,
  "user_role_in_group": ...,
  "user_activity_in_group": ...,
  "user_muted_group": ...,

  # Business context (if business)
  "business_verified": ...,
  "business_category": ...,
  "business_domain": ...,
  "user_has_orders_with_biz": ...,
  "user_opted_in": ...,

  # Media enrichment
  "media_ocr_text": ...,
  "media_vlm_caption": ...,
  "media_category": ...,
  "voice_transcript": ...,

  # History
  "recent_message_history": [...],    # last N messages from this sender/group
  "user_reaction_history": {...},      # open/reply/mute/dismiss counts
}
```

**Inputs:** Master lookup dict + `media_cache.json`  
**Outputs:** List of 110 `MessageContext` objects  

**Risks:** Missing fields for some messages (no group, no business, no media) → populate with `None` / empty string; LLM must gracefully handle sparse context.

---

### Phase 3 — Signal Computation Layer

**Objective:** Compute interpretable numeric and categorical signals per message that feed both the rule engine and the LLM prompt, making decisions more consistent, auditable, and explainable.

**Duration:** 3 hours

**Modules:**

#### 3A — User Preference Signals
- `is_quiet_hours`: bool — is `created_at` within user's quiet hours?
- `notification_fatigue_score`: float 0–1 — derived from `daily_notification_summary.csv` (high if user already received many today)
- `user_engagement_score`: float 0–1 — based on open rate, reply rate in `message_events.csv`

#### 3B — Group Context Signals
- `group_relevance_score`: float — user's activity level in this group (reads, replies) from `group_members.csv`
- `is_admin_message`: bool — sender is group admin
- `group_is_muted_by_user`: bool

#### 3C — Business Reputation Signals
- `business_trust_score`: float 0–1 — verified + domain age + user has prior transactions
- `user_opted_in`: bool
- `business_account_age_days`: int

#### 3D — Risk Scorer (Critical)
- `forward_chain_depth`: int — `forwarded_count` > 3 is a strong scam signal
- `scam_keyword_score`: float — keyword matching against known scam patterns (prize, urgent transfer, OTP, click here, WhatsApp banned, etc.)
- `spam_repetition_score`: float — same sender + similar message in last 24h from `message_history.csv`
- `unverified_business_flag`: bool — business not verified + promotional content
- `risk_level`: `none` | `low` | `medium` | `high` | `critical`

#### 3E — Urgency & Relevance Signals
- `urgency_keywords_present`: bool — keywords like "emergency", "accident", "hospital", "urgent"
- `personal_sender_known`: bool — sender exists in user's conversation history
- `message_length_signal`: `short` | `medium` | `long`

#### 3F — History Similarity (for evidence_message_ids)
- Embed `message_text` using `sentence-transformers`
- Query FAISS index built from `message_history.csv` to find top-3 similar historical messages
- Return their `message_ids` as `candidate_evidence_ids`

#### 3G — Notification Fatigue & Repetition
- `messages_received_today_from_sender`: int
- `repetition_flag`: bool — same/similar message from same group recently

**Inputs:** `MessageContext` per message  
**Outputs:** `SignalBundle` dict added to each `MessageContext`

**Why This Way:** Signals give the LLM structured, pre-computed facts, reducing hallucination and improving consistency. They also power the hard filter layer independently of the LLM.

---

### Phase 4 — Rule-Based Hard Filter (Safety Override)

**Objective:** Catch clear-cut scam, spam, and safety violations before they reach the LLM — ensuring zero tolerance for harmful content routing, and reducing unnecessary API costs.

**Duration:** 1 hour

**Logic:**

```
IF risk_level == "critical"                          → MUTE  (scam)
ELIF scam_keyword_score > 0.8                        → MUTE  (scam)
ELIF forward_chain_depth > 5 AND risk > "low"        → MUTE  (spam/forward)
ELIF unverified_business_flag AND spam_repetition    → MUTE  (promotion/spam)
ELIF is_quiet_hours AND NOT urgency_keywords_present → DIGEST (override to respect quiet hours)
ELIF group_is_muted_by_user AND NOT urgency          → MUTE
ELSE                                                 → pass to LLM
```

**Hard filter outputs a tuple:** `(action, message_type, reason, confidence=0.95)`  
- Confidence is set to 0.95 for hard-filter decisions (high certainty but leave room for edge cases)

**Inputs:** `SignalBundle` per message  
**Outputs:** Routing decision OR `None` (pass-through to LLM)  

**Risk Mitigation:** Hard filters must never block legitimate urgency messages. The urgency keyword check prevents a family emergency message from being muted even if it came during quiet hours from an unfamiliar sender.

---

### Phase 5 — LLM Reasoning Engine (Core)

**Objective:** For all messages not caught by hard filters, use an LLM to perform nuanced, personalized, multimodal contextual reasoning and produce the final routing decision.

**Duration:** 4–5 hours

**Architecture:**

**Prompt Strategy (no full prompts, only structure):**

```
SYSTEM:
  Role: Expert WhatsApp notification router
  Goal: Classify message into notify/digest/mute
  Output format: strict JSON with keys: action, message_type, reason, confidence, evidence_message_ids

USER CONTEXT BLOCK:
  [User profile summary: engagement patterns, quiet hours, fatigue level]

MESSAGE BLOCK:
  [Raw message text + media description/transcript if available]

SENDER/GROUP/BUSINESS BLOCK:
  [Conversation type | Group role | Business trust level | Verified status]

SIGNAL BLOCK:
  [Pre-computed signals: urgency, risk, repetition, forwarding depth]

HISTORY BLOCK:
  [Top 2–3 similar historical messages + user reactions to them]

INSTRUCTION:
  Based on all the above context, decide:
  1. action: notify | digest | mute
  2. message_type: [from allowed list]
  3. reason: 1–2 sentence human-readable explanation
  4. confidence: 0.0–1.0
  5. evidence_message_ids: semicolon-separated historical IDs used as evidence; "none" if none
  Output only valid JSON. No commentary.
```

**Decision Guidelines baked into prompt:**
- Personalization: same message from a known contact vs. unknown business is different
- Mute safety signals regardless of relationship
- Digest means useful but not time-sensitive
- Notify only for genuine urgency or high-relevance personal messages

**Batching Strategy:**
- Process 110 messages in parallel batches of 10 using `asyncio.gather`
- Each call is independent (stateless) — no shared context across messages
- Retry logic: 2 retries on rate-limit or timeout (exponential backoff)

**Output Parsing:**
- Strip markdown fences from LLM response
- Parse JSON safely with `json.loads` + try/except
- Validate `action` is one of `{notify, digest, mute}`
- Validate `message_type` is one of the 12 allowed values
- If parsing fails → fallback to `digest` with `confidence=0.4`

**Inputs:** `MessageContext` + `SignalBundle` (for messages that passed hard filter)  
**Outputs:** Routing decision tuple per message  

**Tools:** `anthropic` Python SDK, `asyncio`, `httpx`

**Risks:**
- LLM may return invalid JSON → robust fallback parser
- Rate limits on 110 calls → batch with sleep between waves
- Inconsistent reasoning → system prompt specifies strict decision hierarchy

**Evaluation / Success Criteria:** All 110 rows have valid, non-empty `action`, `message_type`, `reason` (< 40 words), `confidence` (0–1), `evidence_message_ids`.

---

### Phase 6 — Confidence Calibration

**Objective:** Ensure confidence scores are meaningful, calibrated, and not overconfident — they're evaluated by judges.

**Duration:** 1 hour

**Strategy:**

| Condition | Confidence Adjustment |
|---|---|
| Hard filter fired (clear scam/spam) | 0.90–0.95 |
| LLM decision + strong signal agreement | LLM value (trust it) |
| LLM decision + signals partially disagree | LLM value × 0.85 |
| LLM parsing failed, using fallback | 0.35–0.45 |
| Edge case: no history, no signals, sparse context | Cap at 0.65 |

**Calibration Rule:** If the hard filter and LLM agree → boost confidence by 0.05 (cap at 0.97). If they disagree → use hard filter decision but lower confidence to 0.75 and log the conflict for review.

**Uncertainty Handling:** Sparse context (null group, null business, null media, no history) should always lower confidence. Never output 1.0.

---

### Phase 7 — Evidence Retrieval & Linking

**Objective:** Populate `evidence_message_ids` with relevant historical message IDs that justify the routing decision, exactly as the evaluation criteria require.

**Duration:** 1–2 hours

**Strategy:**
1. From Phase 3F, we already have `candidate_evidence_ids` (FAISS top-3 similar messages)
2. Filter: only include evidence IDs where the user's **reaction** in `message_events.csv` was consistent with the decision (e.g., if routing `mute`, prefer evidence where user previously muted/dismissed similar messages)
3. Include evidence IDs that are from the **same sender or group** where possible
4. If LLM explicitly mentions a historical pattern in its `reason`, cross-reference and include the matching IDs
5. Format: `"msg_012;msg_045;msg_067"` — semicolon-separated, no spaces

**Fallback:** If no strong evidence found → write `"none"` (the spec allows this)

**Why This Matters:** Evidence IDs are explicitly evaluated by judges. Strong evidence = evidence that is topically similar AND where user behavior confirms the routing pattern.

---

### Phase 8 — Output Generation & Validation

**Objective:** Produce a correctly formatted, complete `output.csv` with all 110 rows filled and no format violations.

**Duration:** 1 hour

**Key Tasks:**
- Assemble all decisions into a pandas DataFrame with exact column order:
  `message_id, action, message_type, reason, confidence, evidence_message_ids`
- Validate every row:
  - `action` ∈ {notify, digest, mute}
  - `message_type` ∈ {personal, urgent, event, payment, business_update, promotion, greeting, forward, spam, scam, unknown}
  - `reason` is non-empty string ≤ 50 words
  - `confidence` is float between 0.0 and 1.0
  - `evidence_message_ids` is either `"none"` or semicolon-separated valid message IDs
- Write to `output.csv` without index
- Cross-check that all 110 `message_id` values from input appear in output, in the original order

**Inputs:** Routing decisions from Phases 4 & 5  
**Outputs:** `output.csv` (final submission artifact)

---

### Phase 9 — Logging, Monitoring & Debugging

**Objective:** Maintain a full audit trail of all decisions for debugging and for the `chat_transcript` submission requirement.

**Duration:** Ongoing (built in from Phase 1)

**What to Log:**
- Per-message: all signals, which engine made the decision (hard filter vs. LLM), raw LLM response, parsed output, confidence adjustments
- System-level: total API calls, total tokens, latency per message, retry counts, parsing failures
- Decision distribution: how many `notify` / `digest` / `mute` (judges may check for realistic distributions)

**Format:** JSONL file `run_log.jsonl` — one line per message, full context included

**Monitoring:** Print running tally every 10 messages: `"Processed 40/110 — notify:12 digest:18 mute:10 failures:0"`

**Why This Matters:** The `chat_transcript` submission file should narrate how the system was built and decisions were made. The log feeds this narrative directly.

---

## Evaluation Framework (Offline)

Before final submission, self-evaluate against `sample_messages.csv`:

| Metric | Method | Target |
|---|---|---|
| Action accuracy | Compare predicted `action` vs. `sample_messages.csv` expected | > 80% match |
| Message type accuracy | Same comparison | > 75% match |
| Reason quality | Manual review: is it human-readable & specific? | All < 40 words, non-generic |
| Evidence relevance | Are evidence IDs from same sender/topic? | > 70% relevant |
| Confidence calibration | High confidence → correct? Low → edge case? | Monotonically consistent |
| Distribution sanity | % notify / digest / mute realistic? | ~20% / 40% / 40% rough target |

---

## Risk Mitigation Plan

| Risk | Mitigation |
|---|---|
| LLM hallucinating message types | Provide exact allowed list in every prompt; validate post-parse |
| Overconfidence on sparse context | Cap confidence at 0.65 if < 3 context signals available |
| Missing media files | Graceful fallback: treat as text-only, log missing file |
| API rate limits | Batch of 10, 1s sleep between waves, exponential backoff on 429 |
| Scam bypassing filters | Hard filter runs FIRST, unconditionally; LLM cannot override it |
| Format non-compliance | Strict post-generation validator before writing CSV |
| Same evidence IDs everywhere | FAISS gives per-message unique nearest neighbors |

---

## Innovative Ideas (Impress the Judges)

1. **Behavioral fingerprinting:** Build a per-user "engagement signature" from `message_events.csv` — users who habitually ignore promotions get stricter muting, users who always open business messages get softer business routing.

2. **Conversation arc detection:** If the last 3 messages from a sender were all ignored, down-weight the current one toward `digest` or `mute` even if the content seems relevant.

3. **Media trust scoring:** An image that is highly forwarded AND contains urgency keywords in OCR text AND came from an unverified business = high scam probability — treat as `scam` type, `mute`.

4. **Notification fatigue curve:** Model each user's daily notification load as a curve. Messages arriving when load is already high get pushed to `digest` even if they'd otherwise qualify for `notify`.

5. **Soft scam detection via VLM:** Ask the VLM to rate "does this image look like a scam or lottery notice?" and use that as a standalone scam signal — catches visual scams that have no suspicious text.

---

## Assumptions & Constraints

- All 110 messages in `messages.csv` must be predicted — no skipping allowed
- The LLM has no access to ground truth; it must reason only from context
- `sample_messages.csv` is used **only** to calibrate reasoning style and output format — not as training data
- Media processing is optional but strongly recommended for quality (voice notes especially may carry urgency)
- The system must run end-to-end reproducibly from `messages.csv` + context files as a single pipeline
- Hard filter decisions always take precedence over LLM — this is a safety guarantee
- Confidence of `1.0` is never output — it would imply perfect certainty which no single-pass system can guarantee

---

## Timeline / Roadmap

```
Hour 0–1    │ Phase 0  │ Environment setup, data audit, master dict build
Hour 1–4    │ Phase 1  │ Multimodal preprocessing (OCR, Whisper, VLM)
Hour 4–6    │ Phase 2  │ Context assembler for all 110 messages
Hour 6–9    │ Phase 3  │ Signal computation (all 7 modules)
Hour 9–10   │ Phase 4  │ Hard filter rules (scam/spam/quiet hours)
Hour 10–14  │ Phase 5  │ LLM reasoning engine + async batching
Hour 14–15  │ Phase 6  │ Confidence calibration layer
Hour 15–16  │ Phase 7  │ Evidence retrieval + linking (FAISS + reaction filter)
Hour 16–17  │ Phase 8  │ Output generation + format validation
Hour 17–18  │ Phase 9  │ Logging review, distribution sanity check
Hour 18–20  │ Offline eval against sample_messages.csv + iteration
Hour 20–22  │ Code cleanup, README, chat_transcript write-up, code.zip packaging
```

---

## Submission Checklist

- [ ] `output.csv` — 110 rows, 6 columns, all filled, correct format
- [ ] `code.zip` — Full runnable pipeline with `README.md` explaining how to run
- [ ] `chat_transcript` — Narrative of system design decisions, prompt strategy, iterations
- [ ] `README.md` includes: dependencies, how to run, architecture summary, key decisions

---

*Plan prepared by Vishal Lakshmikanthan — think like a judge, build like a winner.*
