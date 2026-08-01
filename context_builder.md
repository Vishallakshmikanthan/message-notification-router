# Context Builder & MessageContext Schema Specification

## 1. Context Building Subsystem Architecture

The **Context Building Subsystem** is responsible for synthesizing raw incoming messages into fully enriched, immutably bound **`MessageContext`** objects. 

When a raw message arrives from `messages.csv`, it contains minimal attributes (`message_id`, `user_id`, `conversation_type`, `sender_user_id`, `media_id`, etc.). The `ContextBuilder`, orchestrated by `ContextService`, performs a parallel, multi-repository fan-out read across underlying repositories and lookup services to populate a comprehensive 360-degree context object in under **1.0 millisecond**.

```
                           +------------------------+
                           |     Incoming Raw       |
                           |       Message          |
                           +-----------+------------+
                                       |
                                       v
                           +------------------------+
                           |     ContextService     |
                           +-----------+------------+
                                       |
           +---------------------------+---------------------------+
           |                           |                           |
           v                           v                           v
+--------------------+   +--------------------+   +--------------------+
|  UserLookupService |   |ChannelLookupService|   |HistoryLookupService|
+----------+---------+   +----------+---------+   +----------+---------+
           |                           |                           |
           +---------------------------+---------------------------+
                                       |
                                       v
                           +------------------------+
                           |     ContextBuilder     |
                           +-----------+------------+
                                       |
                                       v
                           +------------------------+
                           |  Immutable Enriched    |
                           |     MessageContext     |
                           +------------------------+
```

---

## 2. Complete `MessageContext` Field Specification Matrix

The following matrix documents every single attribute of the enriched `MessageContext` object, its data type, nullability contract, populating lookup service, downstream consuming modules, and architectural rationale.

| Category | Field Name | Data Type | Nullable? | Populating Subsystem | Downstream Consumer Modules | Architectural Rationale & Description |
|---|---|---|---|---|---|---|
| **Primary Metadata** | `message_id` | String | NO | `MessageRepository` | All Modules | Unique identifier of the incoming evaluation message (`msg_001`). |
| | `created_at` | Timestamp | NO | `MessageRepository` | Signal Engine, Router | Exact arrival timestamp of message (`YYYY-MM-DD HH:MM:SS`). |
| | `conversation_type` | Enum | NO | `MessageRepository` | Channel Lookup, Router | Conversation modality (`personal`, `group`, `business`). |
| | `forwarded_count` | Integer | NO | `MessageRepository` | Signal Engine, Risk Engine | Count of message re-forwards. High values indicate viral/spam potential. |
| | `message_text` | String | YES | `MessageRepository` | Text Processors, Feature Engines | Raw UTF-8 text string payload. NULL for pure media messages. |
| **Recipient Profile** | `user_id` | String | NO | `UserLookupService` | All Modules | Recipient user primary key (`u_001`). |
| | `user_dnd_window` | String | NO | `UserLookupService` | Decision Engine, Router | Preferred quiet hours range (e.g. `22:00-07:00`). |
| | `user_messages_opened_30d` | Integer | NO | `UserLookupService` | Signal Engine | Global user message open count over 30 days. |
| | `user_messages_replied_30d` | Integer | NO | `UserLookupService` | Signal Engine | Global user reply count over 30 days. |
| | `user_notifications_dismissed_30d` | Integer | NO | `UserLookupService` | Signal Engine | Global notification dismissal count over 30 days. |
| | `user_messages_reported_30d` | Integer | NO | `UserLookupService` | Risk Engine, Router | Global spam/scam report count filed by user in 30 days. |
| **Channel Context (Personal)**| `sender_user_id` | String | YES | `ChannelLookupService` | History Lookup, Router | Sender user ID if personal/group chat. NULL for business. |
| | `sender_user_profile` | Object | YES | `UserLookupService` | Feature Engine | Full profile object of the sender user when applicable. |
| **Channel Context (Group)** | `group_id` | String | YES | `ChannelLookupService` | Group Manager, Router | Target group identifier if `conversation_type == 'group'`. |
| | `group_name` | String | YES | `ChannelLookupService` | Notification UI | Human-readable title of the group. |
| | `group_type` | Enum | YES | `ChannelLookupService` | Signal Engine, Router | Categorical type (`family`, `coworker`, `society`, etc.). |
| | `group_member_count` | Integer | YES | `ChannelLookupService` | Signal Engine | Total participants in group. |
| | `group_admin_count` | Integer | YES | `ChannelLookupService` | Feature Engine | Total administrators in group. |
| | `user_group_role` | Enum | YES | `ChannelLookupService` | Router, Decision Engine | Recipient's role in group (`admin` vs `member`). |
| | `user_group_muted` | Boolean | YES | `ChannelLookupService` | Router, Override Engine | Explicit user mute flag (`true` if muted by user). |
| | `user_group_sent_30d` | Integer | YES | `ChannelLookupService` | Signal Engine | Messages sent by user in this group over 30 days. |
| | `user_group_read_30d` | Integer | YES | `ChannelLookupService` | Signal Engine | Messages read by user in this group over 30 days. |
| **Channel Context (Business)**| `business_id` | String | YES | `ChannelLookupService` | Business Engine, Router | Target business account ID if `conversation_type == 'business'`. |
| | `business_display_name` | String | YES | `ChannelLookupService` | Notification UI | Display title of the business entity. |
| | `business_category` | Enum | YES | `ChannelLookupService` | Signal Engine, Categorizer | Business category (`ecommerce_delivery`, `bank`, etc.). |
| | `business_verified` | Boolean | YES | `ChannelLookupService` | Risk Engine, Router | Official verification green-tick status. |
| | `official_domain` | String | YES | `ChannelLookupService` | Risk Engine | Registered official domain name (`amazon.in`). |
| | `domain_used_by_sender` | String | YES | `ChannelLookupService` | Risk Engine, Auditor | Domain embedded by sender (`amazonpay-delivery.in`). |
| | `domain_mismatch_flag` | Boolean | YES | `ChannelLookupService` | Risk Engine, Router | `true` if `official_domain != domain_used_by_sender`. |
| | `why_user_knows_account` | String | YES | `ChannelLookupService` | Context Summarizer | Relationship origin explanation. |
| | `allows_promotions` | Boolean | YES | `ChannelLookupService` | Decision Engine, Router | User promotional consent indicator. |
| | `promotions_opted_out_at` | Timestamp | YES | `ChannelLookupService` | Decision Engine | Timestamp when user opted out of promotional alerts. |
| **Media Metadata** | `media_type` | Enum | YES | `MediaRepository` | Media Handlers, Classifiers | Attached media modality (`image`, `voice`, or NULL). |
| | `media_id` | String | YES | `MediaRepository` | Media Handlers | Primary key of media asset manifest. |
| | `media_file_path` | String | YES | `FileManager` | Binary Readers | Verified relative physical disk path pointer. |
| | `media_disk_exists` | Boolean | YES | `FileManager` | Risk Engine, Handlers | `true` if media binary file exists on physical disk. |
| **Interaction History** | `history_total_messages` | Integer | NO | `HistoryLookupService` | Signal Engine | Historical message count between user and sender/business. |
| | `history_user_replies_count` | Integer | NO | `HistoryLookupService` | Signal Engine | Count of direct user replies in history trajectory. |
| | `history_last_interaction_at` | Timestamp | YES | `HistoryLookupService` | Feature Engine | Timestamp of last recorded user interaction. |
| | `history_days_since_last_interaction`| Double | YES | `HistoryLookupService` | Signal Engine | Recency delta in fractional days. |
| **Daily Metrics Baseline** | `daily_avg_received` | Double | NO | `HistoryLookupService` | Signal Engine | Average daily notifications received by recipient. |
| | `daily_avg_dismissed` | Double | NO | `HistoryLookupService` | Signal Engine | Average daily notifications dismissed by recipient. |
| | `daily_dismissal_rate` | Double | NO | `HistoryLookupService` | Decision Engine | Ratio of dismissed notifications (`dismissed / received`). |

---

## 3. Fallback & Default Profile Injection

When optional relations are missing or referential anomalies occur:
- **Missing Group Membership**: If a group message arrives from a sender not indexed in `group_members.csv`, `ContextBuilder` sets `user_group_role = 'member'`, `user_group_muted = false`, and logs a Level 3 schema warning.
- **Missing Business History**: If a business message arrives without a prior record in `user_business_history.csv`, default attributes are assigned: `why_user_knows_account = 'unknown'`, `allows_promotions = false`, `activity_count_180d = 0`.
- **Missing Media File**: If manifest pointer exists but file is absent on disk, `media_disk_exists = false` and `media_file_path = NULL`.

---

## 4. Downstream Interface Contracts

1. **Immutability Contract**: `MessageContext` instances are strictly read-only post-construction. Mutating context fields downstream is forbidden.
2. **Zero-Copy Pass-by-Reference**: Downstream consuming modules receive direct reference pointers to the instantiated `MessageContext`, avoiding memory copying overhead.
3. **Thread Isolation**: Each evaluation message receives its own dedicated `MessageContext` instance, ensuring thread safety during multi-threaded batch processing.
