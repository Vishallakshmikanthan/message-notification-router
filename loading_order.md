# Deterministic Data Loading & Indexing Blueprint

## Overview
This document specifies the exact execution sequence, in-memory index construction, schema validation steps, and caching strategy for booting up the WhatsApp Message Notification Router data layer.

---

## 1. Deterministic 7-Stage Loading Pipeline

```
[ Stage 1: Physical Media Audit ]
       |
       v
[ Stage 2: Load Static Reference Tables ] (users.csv, groups.csv, business_accounts.csv)
       |
       v
[ Stage 3: Load Junction Tables ] (group_members.csv, user_business_history.csv)
       |
       v
[ Stage 4: Load Media Pointer Manifests ] (images.csv, voice_notes.csv)
       |
       v
[ Stage 5: Load Historical Corpus & Events ] (message_history.csv, message_events.csv)
       |
       v
[ Stage 6: Load Time-Series Metrics ] (daily_notification_summary.csv)
       |
       v
[ Stage 7: Stream / Batch Primary Dataset ] (messages.csv)
```

---

## 2. Detailed Execution Sequence & Index Construction

### Stage 1: Physical Media Audit & Asset Indexing
- **Action**: Scan `dataset/media/images/` and `dataset/media/audio/`.
- **Validation**: Assert directory existence and file readability.
- **Index Built**: `Set[file_path]` for O(1) disk existence validation.

### Stage 2: Static Base Entity Loading
1. **`users.csv`**:
   - Parse CSV into memory. Validate 55 user profiles.
   - **Index Built**: `UserMap: Dict[user_id, UserProfile]`.
2. **`groups.csv`**:
   - Parse CSV into memory. Validate 24 group profiles.
   - **Index Built**: `GroupMap: Dict[group_id, GroupProfile]`.
3. **`business_accounts.csv`**:
   - Parse CSV into memory. Validate 111 business profiles.
   - **Index Built**: `BusinessMap: Dict[business_id, BusinessProfile]`.

### Stage 3: Junction & Relationship Table Loading
1. **`group_members.csv`**:
   - Validate FK dependencies (`group_id` in `GroupMap`, `user_id` in `UserMap`).
   - **Indexes Built**:
     - `GroupMemberMap: Dict[(group_id, user_id), GroupMemberRecord]` O(1) lookup.
     - `GroupAdminSet: Set[(group_id, user_id)]` for instant admin verification.
     - `UserGroupList: Dict[user_id, List[group_id]]` for reverse lookup.
2. **`user_business_history.csv`**:
   - Validate FK dependencies (`user_id` in `UserMap`, `business_id` in `BusinessMap`).
   - **Index Built**: `UserBusinessMap: Dict[(user_id, business_id), UserBusinessRecord]`.

### Stage 4: Media Manifest Resolution
1. **`images.csv`**:
   - Verify every `file_path` exists in `Set[file_path]` from Stage 1.
   - **Index Built**: `ImageMap: Dict[image_id, file_path]`.
2. **`voice_notes.csv`**:
   - Verify every `file_path` exists in `Set[file_path]` from Stage 1.
   - **Index Built**: `VoiceNoteMap: Dict[voice_note_id, file_path]`.

### Stage 5: Historical Message Corpus & Event Log Indexing
1. **`message_history.csv`**:
   - Parse historical text messages.
   - **Indexes Built**:
     - `MessageHistoryMap: Dict[message_id, MessageRecord]`.
     - `UserHistoryIndex: Dict[user_id, List[MessageRecord]]` sorted by `created_at`.
     - `SenderHistoryIndex: Dict[(user_id, sender_id), List[MessageRecord]]`.
     - `BusinessHistoryIndex: Dict[(user_id, business_id), List[MessageRecord]]`.
2. **`message_events.csv`**:
   - Validate FK `message_id` in `MessageHistoryMap`.
   - **Index Built**: `MessageEventsMap: Dict[(user_id, message_id), EventRecord]`.

### Stage 6: Aggregated Time-Series Loading
1. **`daily_notification_summary.csv`**:
   - Parse time-series metrics per user date.
   - **Index Built**: `DailySummaryMap: Dict[(user_id, date), SummaryRecord]`.

### Stage 7: Primary Stream Processing (`messages.csv`)
- Iterate through `messages.csv` row by row.
- For each message:
  1. Perform O(1) lookup in `UserMap` for recipient profile.
  2. Resolve channel context via O(1) lookups in `GroupMap` / `GroupMemberMap` or `BusinessMap` / `UserBusinessMap`.
  3. Retrieve historical evidence from `UserHistoryIndex` and `MessageEventsMap`.
  4. Perform downstream routing evaluation.

---

## 3. Caching & Memory Optimization Rules

- **Zero DB Roundtrips**: Total RAM required for all CSV index data structures is < 5 MB. The entire dataset fits comfortably in memory.
- **Pre-computed Lookups**: Hash maps (`Dict`) and sets (`Set`) provide $O(1)$ query complexity for all identity, relationship, and mute checks during inference.
- **Multimodal Lazy Loading**: Media binary files (images/audio) are loaded lazily on-demand via disk paths in `ImageMap`/`VoiceNoteMap`, preserving memory during text-only message routing.
