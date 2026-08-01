# Dataset Exploration & Discovery Report

## Executive Summary
This document provides the foundational data exploration report for the WhatsApp Message Notification Router system. It defines the dataset topology, entity models, schema definitions, memory footprints, and architectural considerations required prior to pipeline implementation.

---

## 1. Core Inspection Priority & Order

### Priority 1: Primary Transaction Table
* **`messages.csv`**: The primary inference target dataset. Every row represents an incoming message that requires a notification routing decision (`notify`, `digest`, `mute`).

### Priority 2: Base Entity Registries
1. **`users.csv`**: Master list of message recipients and their global notification profile (quiet hours, 30-day baseline interactions).
2. **`groups.csv`**: Master registry of WhatsApp groups (group names, member counts, admin counts, creation dates).
3. **`business_accounts.csv`**: Master registry of business senders (brand names, verification status, domain authenticity, sender domain age, report counts).

### Priority 3: Relationship & Junction Tables
1. **`group_members.csv`**: Relationship matrix mapping Users to Groups (user role, join date, group-level mute status, 30-day read/reply metrics).
2. **`user_business_history.csv`**: Relationship matrix mapping Users to Businesses (interaction history, opt-in/opt-out status, last activity date).

### Priority 4: Historical & Event Logs
1. **`message_history.csv`**: Past message corpus used for contextual retrieval, pattern recognition, and evidence gathering.
2. **`message_events.csv`**: User interaction log linked to `message_history.csv` (opens, replies, dismissals, mutes, reports).
3. **`daily_notification_summary.csv`**: Time-series log tracking daily notification density and dismissal ratios per user.

### Priority 5: Media Pointer Tables & Raw Media Assets
1. **`images.csv`**: Image manifest pointing to binary assets in `media/images/`.
2. **`voice_notes.csv`**: Audio manifest pointing to binary assets in `media/audio/`.
3. **`dataset/media/`**: Physical directory containing image (.jpg) and audio (.mp3) files.

### Priority 6: Reference & Submission Templates
1. **`sample_messages.csv`**: Ground truth gold-standard reference examples with ideal routing actions, classifications, reasons, and evidence IDs.
2. **`output.csv`**: Target output template structure for model submission.

---

## 2. Dataset Dependencies & Topology

```
                  +-------------------+        +-------------------+
                  |     users.csv     |        |    groups.csv     |
                  +---------+---------+        +---------+---------+
                            |                            |
                            +------------+  +------------+
                                         |  |
                                +--------v--v--------+
                                | group_members.csv  |
                                +--------------------+

                  +-------------------+        +-------------------+
                  |     users.csv     |        |business_accounts  |
                  +---------+---------+        +---------+---------+
                            |                            |
                            +------------+  +------------+
                                         |  |
                                +--------v--v--------+
                                |user_business_hist. |
                                +--------------------+

+-------------------+   +--------------------+   +--------------------+
|    images.csv     |   |  voice_notes.csv   |   |   users / groups   |
+---------+---------+   +---------+----------+   | business_accounts  |
          |                       |              +---------+----------+
          +-----------+   +-------+                        |
                      |   |                                |
             +--------v---v--------+                       |
             |    messages.csv     |<----------------------+ (FK Dependencies)
             | (Primary Transaction)|
             +---------------------+

             +---------------------+
             | message_history.csv |<------------------+ (Historical Corpus)
             +----------+----------+                   |
                        |                              |
             +----------v----------+                   |
             | message_events.csv  |                   |
             +---------------------+                   |
                                                       |
             +---------------------+                   |
             |daily_notification_  |                   |
             |    summary.csv      |                   |
             +---------------------+                   |
```

---

## 3. Storage, Memory & Usage Profiling

| Dataset File | File Size (Approx) | Total Rows | Memory Footprint (RAM) | Primary Key / Natural Key | Recommended Cache Strategy | Query Frequency |
|---|---|---|---|---|---|---|
| `messages.csv` | ~23.2 KB | 265 | < 500 KB | `message_id` | Streaming / Batch Processing | High (Inference Loop) |
| `users.csv` | ~1.7 KB | 55 | < 100 KB | `user_id` | Fully In-Memory (Hash Table) | High (Every Message) |
| `groups.csv` | ~1.6 KB | 24 | < 50 KB | `group_id` | Fully In-Memory (Hash Table) | High (Group Messages) |
| `business_accounts.csv` | ~9.7 KB | 111 | < 200 KB | `business_id` | Fully In-Memory (Hash Table) | High (Business Messages) |
| `group_members.csv` | ~18.4 KB | 402 | < 300 KB | `(group_id, user_id)` | Fully In-Memory Multi-Index | High (Group Messages) |
| `user_business_history.csv` | ~9.0 KB | 107 | < 200 KB | `(user_id, business_id)` | Fully In-Memory Composite Map | High (Business Messages) |
| `message_history.csv` | ~77.0 KB | 1,063 | ~1.5 MB | `message_id` | In-Memory / Vector Indexed | High (Evidence Retrieval) |
| `message_events.csv` | ~13.4 KB | 413 | < 250 KB | `(user_id, message_id)` | Fully In-Memory Composite Map | Medium (Historical Context) |
| `images.csv` | ~0.7 KB | 21 | < 20 KB | `image_id` | Cache Metadata Path | On-demand (Multimodal) |
| `voice_notes.csv` | ~0.4 KB | 14 | < 15 KB | `voice_note_id` | Cache Metadata Path | On-demand (Multimodal) |
| `daily_notification_summary.csv` | ~16.8 KB | 757 | < 300 KB | `(user_id, date)` | Pre-aggregated Summary Dict | Low / Medium (User state) |
| `sample_messages.csv` | ~10.0 KB | 71 | < 200 KB | `message_id` | Reference / Few-Shot Pool | Static (System Warmup) |

---

## 4. Key Architectural Discoveries

1. **Polymorphic Sender Design**:
   - Incoming messages in `messages.csv` can originate from three mutually exclusive conversation types: `personal`, `group`, or `business`.
   - When `conversation_type == 'personal'`, `sender_user_id` is populated while `group_id` and `business_id` are NULL.
   - When `conversation_type == 'group'`, `group_id` and `sender_user_id` are populated while `business_id` is NULL.
   - When `conversation_type == 'business'`, `business_id` is populated while `group_id` and `sender_user_id` are NULL.

2. **Multimodal Media Pointers**:
   - `media_type` takes values `image`, `voice`, or NULL/empty string.
   - When `media_type == 'image'`, `media_id` references `images.csv` (`image_id`). `message_text` may be empty or contain a caption.
   - When `media_type == 'voice'`, `media_id` references `voice_notes.csv` (`voice_note_id`). `message_text` is typically empty.

3. **Multi-line Text Quotes & Escaping**:
   - Text fields in `messages.csv`, `message_history.csv`, and `sample_messages.csv` contain embedded newline characters (`\n`), commas, and quotation marks.
   - CSV parsers must strictly adhere to RFC 4180 rules (handling standard double-quote escaping) to prevent record corruption and line offset errors.

4. **Domain Identity & Spoofing Signals**:
   - `business_accounts.csv` contains `official_domain` and `domain_used_by_sender`.
   - Mismatches between `official_domain` and `domain_used_by_sender` (e.g. `phonepe.com` vs `phonepe-rewards.in`) combined with low `domain_used_by_sender_age_days` (e.g. 7 days) serve as immediate domain spoofing / phishing risk indicators.
