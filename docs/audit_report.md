# Data Audit & Quality Control Plan

## Overview
This document outlines the software engineering audit protocol, diagnostic checklists, integrity checks, and edge-case hazard matrices for the WhatsApp Message Notification Router dataset.

---

## 1. Automated Data Audit Checklist

### A. Missing Values & Nullability Audits
- [ ] Verify `messages.csv`: `message_id`, `user_id`, `conversation_type`, `created_at`, `forwarded_count` MUST contain ZERO nulls.
- [ ] Validate conditional NULL constraints:
  - If `conversation_type == 'group'`, `group_id` must NOT be NULL.
  - If `conversation_type == 'business'`, `business_id` must NOT be NULL.
  - If `conversation_type == 'personal'`, `group_id` and `business_id` MUST be NULL.
  - If `media_type` IS NOT NULL, `media_id` MUST NOT be NULL.
- [ ] Check text completeness: Voice note messages can have NULL `message_text`, but pure text messages MUST NOT have NULL or empty string `message_text`.

### B. Primary Key & Duplicate Audits
- [ ] `messages.csv`: Assert unique `message_id`. Check zero duplicate rows.
- [ ] `users.csv`: Assert unique `user_id`. (Expected count: 55).
- [ ] `groups.csv`: Assert unique `group_id`. (Expected count: 24).
- [ ] `business_accounts.csv`: Assert unique `business_id`. (Expected count: 111).
- [ ] `group_members.csv`: Assert composite unique constraint on `(group_id, user_id)`.
- [ ] `user_business_history.csv`: Assert composite unique constraint on `(user_id, business_id)`.
- [ ] `message_history.csv`: Assert unique `message_id`.
- [ ] `message_events.csv`: Assert composite unique constraint on `(user_id, message_id)`.
- [ ] `daily_notification_summary.csv`: Assert composite unique constraint on `(user_id, date)`.

### C. Foreign Key & Referential Integrity Audits
- [ ] Audit `messages.user_id` -> `users.user_id`: 0 orphaned records allowed.
- [ ] Audit `messages.group_id` -> `groups.group_id`: 0 orphaned group IDs allowed.
- [ ] Audit `messages.business_id` -> `business_accounts.business_id`: 0 orphaned business IDs allowed.
- [ ] Audit `messages.sender_user_id` -> `users.user_id`: 0 orphaned sender user IDs allowed.
- [ ] Audit `group_members.user_id` -> `users.user_id` & `group_members.group_id` -> `groups.group_id`.
- [ ] Audit `user_business_history.user_id` -> `users.user_id` & `user_business_history.business_id` -> `business_accounts.business_id`.
- [ ] Audit `message_events.message_id` -> `message_history.message_id`.
- [ ] Audit `message_events.user_id` against `message_history.user_id` for recipient consistency.

### D. Physical Media Existence & Path Validation
- [ ] `images.csv`: For every row, assert `file_path` exists on disk at `dataset/media/images/<file_name>`. Assert file size > 0 bytes.
- [ ] `voice_notes.csv`: For every row, assert `file_path` exists on disk at `dataset/media/audio/<file_name>`. Assert file size > 0 bytes.
- [ ] Detect unreferenced media files: Check if any `.jpg` or `.mp3` files exist in `media/` that are missing from `images.csv` or `voice_notes.csv`.

### E. Timestamp & Temporal Consistency Audits
- [ ] Verify timestamp formatting: `YYYY-MM-DD HH:MM:SS` across `messages.csv` and `message_history.csv`.
- [ ] Temporal Order Integrity: Assert `created_at` of `messages.csv` >= historical timestamps in `message_history.csv`. (Historical messages must be strictly in the past).
- [ ] Group membership join date check: Assert `group_members.joined_at` <= `groups.created_at` or logically valid.
- [ ] Business promotion opt-out check: IF `promotions_opted_out_at` IS NOT NULL, verify `allows_promotions == 0`.

### F. Domain Identity & Fraud Detection Checks
- [ ] Domain mismatch audit in `business_accounts.csv`: Compare `official_domain` vs `domain_used_by_sender`. Flag all records where `official_domain != domain_used_by_sender`.
- [ ] Domain age audit: Check `domain_used_by_sender_age_days`. Identify newly registered domains (< 30 days) with high message volumes or reports.

---

## 2. Suspicious Patterns & Data Imbalance Hazards

1. **Phishing / Domain Spoofing Hazards**:
   - Example: `business_041` (PhonePe Cashback Desk) has `official_domain = phonepe.com` but `domain_used_by_sender = phonepe-rewards.in`, `account_age_days = 28`, `domain_used_by_sender_age_days = 7`, and `verified = 0`. This is a classic scam pattern.

2. **Viral Forwarding & Spam Patterns**:
   - Messages with `forwarded_count > 5` or `forwarded_count > 10` (e.g. good morning family group forwards) represent low-priority or repetitive noise (`digest` or `mute`).

3. **Quiet Hours Alignment**:
   - Parse `users.do_not_disturb_window` (e.g., `22:00-07:00`). Calculate whether `created_at` timestamp falls within the recipient's DND window. Non-urgent messages during DND should default to `digest` or `mute`.

4. **Group Admin Privilege & Operational Urgency**:
   - Check if `sender_user_id` has `role == 'admin'` in `group_members.csv`. Updates from admins (e.g. society maintenance, water supply shutoff, school bus timing changes) carry high priority (`notify`).

5. **Multi-line Text Parsing Anomalies**:
   - CSV rows with unescaped newline characters or unbalanced double quotes will misalign columns. The audit script must validate row column count consistency (exactly 11 columns for `messages.csv`).
