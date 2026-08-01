# Fast-Path Lookup Services & Relationship Resolution Specification

## 1. Overview & Architectural Role

**Lookup Services** sit directly above raw entity Repositories and below the `ContextBuilder`. While Repositories manage raw entity collections, Lookup Services act as enriched query engines that perform relational resolution, composite key matching, multi-repository joins, and pre-calculated metric computations in constant time O(1).

```
+-------------------------------------------------------------------------+
|                              ContextBuilder                             |
+------------------------------------+------------------------------------+
                                     |
    +--------------------------------+--------------------------------+
    |                                |                                |
    v                                v                                v
+-----------------------+  +-----------------------+  +-----------------------+
|   UserLookupService   |  | ChannelLookupService  |  | HistoryLookupService  |
+-----------+-----------+  +-----------+-----------+  +-----------+-----------+
            |                          |                          |
    +-------+-------+          +-------+-------+          +-------+-------+
    |               |          |       |       |          |       |       |
    v               v          v       v       v          v       v       v
[UserRepo]    [SummaryRepo] [GroupRepo][BusinessRepo] [HistRepo][EventRepo][MediaRepo]
```

---

## 2. Service Specifications

---

### 2.1 `UserLookupService`

#### Purpose & Scope
Provides enriched recipient user profile resolution, global 30-day interaction activity ratios, and quiet-hours window evaluation (`do_not_disturb_window`).

#### Public Method Contracts
- **`GetUserProfile(String userId) -> UserProfile`**:
  - Performs primary lookup in `UserRepository`.
  - Returns `User` entity or default fallback user.
- **`EvaluateDNDStatus(String userId, Timestamp timestamp) -> DNDEvaluation`**:
  - Parses `do_not_disturb_window` string (e.g. `22:00-07:00`).
  - Evaluates whether the incoming timestamp falls within the quiet hours window (handling overnight wraps e.g. 22:00 to 07:00).
  - Returns structured evaluation result (`is_dnd_active: Boolean`, `window_start: Time`, `window_end: Time`).
- **`GetUserActivityMetrics(String userId) -> UserActivityMetrics`**:
  - Calculates global engagement ratios:
    - `OpenRate = messages_opened_30d / (messages_opened_30d + notifications_dismissed_30d)`
    - `ReplyRate = messages_replied_30d / messages_opened_30d`
    - `ReportRatio = messages_reported_30d / messages_opened_30d`

---

### 2.2 `ChannelLookupService`

#### Purpose & Scope
Provides unified channel context resolution across Personal, Group, and Business conversation modalities.

#### Public Method Contracts

#### 1. `ResolvePersonalChannel(String userId, String senderUserId) -> PersonalChannelContext`
- Fetches sender profile from `UserRepository`.
- Computes mutual groups count by intersecting group lists of `userId` and `senderUserId`.
- Retrieves historical interaction trajectory summary from `HistoryLookupService`.

#### 2. `ResolveGroupChannel(String userId, String groupId) -> GroupChannelContext`
- Fetches group metadata from `GroupRepository`.
- Performs composite O(1) lookup in `GroupRepository` for junction tuple `(groupId, userId)`.
- Resolves user-specific group parameters:
  - `role` (`admin` vs `member`)
  - `group_muted_by_user` (Boolean)
  - Member engagement stats (`messages_sent_30d`, `messages_read_30d`, `replies_sent_30d`, `notifications_dismissed_30d`).
- If member record is missing, returns safe default membership profile.

#### 3. `ResolveBusinessChannel(String userId, String businessId) -> BusinessChannelContext`
- Fetches business account profile from `BusinessRepository`.
- Performs composite O(1) lookup in `BusinessRepository` for junction tuple `(userId, businessId)`.
- Resolves domain integrity verification parameters:
  - Evaluates string inequality: `domain_mismatch_flag = (official_domain != domain_used_by_sender)`.
  - Resolves domain registration age delta (`domain_used_by_sender_age_days`).
- Resolves user promotional consent:
  - Validates `allows_promotions` flag and `promotions_opted_out_at` timestamp.

---

### 2.3 `HistoryLookupService`

#### Purpose & Scope
Retrieves and aggregates interaction trajectory histories between users and senders/businesses, as well as time-series daily notification baselines.

#### Public Method Contracts

#### 1. `GetInteractionTrajectory(String userId, String senderOrBusinessId) -> TrajectorySummary`
- Queries `HistoryRepository` using composite key `(userId, senderOrBusinessId)`.
- Computes trajectory metrics:
  - `total_messages_exchanged`
  - `user_replies_count`
  - `last_interaction_timestamp`
  - `days_since_last_interaction = (CurrentTimestamp - last_interaction_timestamp) in Days`

#### 2. `GetDailyNotificationBaseline(String userId, Date date) -> DailyBaselineMetrics`
- Queries `NotificationSummaryRepository` using composite key `(userId, date)`.
- If date specific record missing, queries past 30-day trajectory for `userId` to compute rolling average daily metrics (`avg_received_per_day`, `avg_dismissed_per_day`).

---

## 3. Relationship Resolution Algorithms & O(1) Index Execution

### 3.1 Composite Key Matching
All junction relationships maintain in-memory hash maps keyed by immutable 2-tuples:
```
GroupMemberMap:    Tuple<group_id, user_id>    -> GroupMemberRecord
UserBusinessMap:   Tuple<user_id, business_id> -> UserBusinessRecord
EventMap:          Tuple<user_id, message_id>  -> EventRecord
SummaryMap:        Tuple<user_id, date>        -> DailySummaryRecord
```
- Hash codes for tuple keys are pre-computed using bit-shifting arithmetic (`(hash(id1) * 31) ^ hash(id2)`), guaranteeing fast constant-time lookup without dynamic string concatenation overhead.

### 3.2 Fast-Path Multi-Index Query Pipelines
When `ChannelLookupService` receives a group message:
1. `GroupRepository.GetById(group_id)` -> O(1) lookup.
2. `GroupRepository.GetMember(group_id, user_id)` -> O(1) composite tuple lookup.
3. `GroupRepository.IsAdmin(group_id, user_id)` -> O(1) hash set membership check.
4. Total execution time: < **0.05 milliseconds**.
