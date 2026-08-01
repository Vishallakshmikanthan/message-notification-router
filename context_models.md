# Sub-Context Data Contracts & Models Specification

## 1. Document Overview

This document provides explicit data contracts for all 9 specialized sub-context objects that compose the master `MessageContext`. Each sub-context is an immutable, self-contained model encapsulating a specific domain area of context.

---

## 2. `UserContext` Model

The `UserContext` encapsulates identity, settings, contact status, and account metadata for a specific user (Sender or Receiver).

### Data Source Mapping
Primary: `users.csv` (`user_id`, `name`, `phone_number`, `user_type`, `registration_date`, `preferred_language`, `timezone`)

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `user_id` | `String` | Unique User UUID | No | `users.csv` | Primary identifier for the user. |
| `display_name` | `String` | Non-empty string | No | `users.csv` | Full profile name or fallback label (`"Unknown User"`). |
| `phone_number` | `String` | E.164 format (`+1...`) | No | `users.csv` | Sanitized telephone number. |
| `user_type` | `String (Enum)`| `"INDIVIDUAL"`, `"BUSINESS"`, `"SYSTEM_BOT"` | No | `users.csv` | Categorization of account type. |
| `registration_timestamp`| `Int` | Epoch milliseconds | No | `users.csv` | Account creation timestamp. |
| `account_age_days` | `Int` | $\ge 0$ | No | Computed | Calculated age of the user account in days. |
| `preferred_language` | `String` | ISO 639-1 (`"en"`, `"hi"`, `"es"`) | No | `users.csv` | User's preferred communication language. |
| `timezone` | `String` | IANA Timezone (`"Asia/Kolkata"`) | No | `users.csv` | Standard timezone string for temporal conversions. |
| `is_verified` | `Boolean` | `True` / `False` | No | `users.csv` | Account identity verification status flag. |
| `is_registered_user` | `Boolean` | `True` / `False` | No | System | Flag indicating if user exists in `users.csv` database. |

---

## 3. `GroupContext` Model

The `GroupContext` encapsulates workspace, group type, participant structure, and sender role within a group chat.

### Data Source Mapping
Primary: `groups.csv` (`group_id`, `group_name`, `group_type`, `created_at`, `total_members`, `is_announcement_only`)
Secondary: `group_members.csv` (`group_id`, `user_id`, `role`, `joined_at`, `is_muted`)

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `group_id` | `String` | Unique Group UUID / `"NONE"` | No | `groups.csv` | Primary identifier of the group. |
| `group_name` | `String` | Text string | No | `groups.csv` | Title of the group chat. |
| `group_type` | `String (Enum)`| `"FAMILY"`, `"WORK"`, `"COMMUNITY"`, `"COMMERCIAL"`, `"DIRECT_CHAT"` | No | `groups.csv` | System taxonomy classification of group. |
| `created_at_timestamp` | `Int` | Epoch milliseconds | No | `groups.csv` | Group creation epoch timestamp. |
| `total_member_count` | `Int` | $\ge 0$ | No | `groups.csv` | Total count of registered group members. |
| `is_announcement_only` | `Boolean` | `True` / `False` | No | `groups.csv` | Flag indicating if only admins can post. |
| `sender_role` | `String (Enum)`| `"ADMIN"`, `"MEMBER"`, `"NON_MEMBER"` | No | `group_members.csv` | Specific role of message sender in this group. |
| `sender_joined_at` | `Int` | Epoch milliseconds | No | `group_members.csv` | Epoch timestamp when sender joined group. |
| `sender_is_muted_in_group`| `Boolean` | `True` / `False` | No | `group_members.csv` | Flag indicating if sender has muted this group. |

---

## 4. `BusinessContext` Model

The `BusinessContext` encapsulates commercial account verification, vertical, response SLA, and catalog status.

### Data Source Mapping
Primary: `business_accounts.csv` (`business_id`, `business_name`, `category`, `verification_status`, `support_email`, `catalog_enabled`, `response_time_minutes`)

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `business_id` | `String` | Unique Business ID / `"NONE"` | No | `business_accounts.csv` | Primary commercial identifier. |
| `business_name` | `String` | Text string | No | `business_accounts.csv` | Registered business trade name. |
| `category` | `String (Enum)`| `"RETAIL"`, `"BANKING"`, `"SERVICES"`, `"HEALTHCARE"`, `"NON_BUSINESS"` | No | `business_accounts.csv` | Industry category code. |
| `verification_status` | `String (Enum)`| `"VERIFIED_OFFICIAL"`, `"STANDARD"`, `"UNVERIFIED"` | No | `business_accounts.csv` | WhatsApp official verification badge level. |
| `support_email` | `String` | Email address format | No | `business_accounts.csv` | Official customer support email contact. |
| `catalog_enabled` | `Boolean` | `True` / `False` | No | `business_accounts.csv` | Indicates if business has active WhatsApp catalog. |
| `expected_sla_minutes` | `Int` | $\ge 0$ | No | `business_accounts.csv` | Average response time SLA in minutes. |
| `is_business_account` | `Boolean` | `True` / `False` | No | System | Discriminator flag for business account presence. |

---

## 5. `MediaContext` Model

The `MediaContext` unifies visual OCR, acoustic voice analysis, and multimodal metadata extracted in previous execution phases.

### Data Source Mapping
Primary: `MediaContext`, `ImageContext`, `VoiceContext` objects from Multimodal Intelligence Layer.

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `media_id` | `String` | Asset ID / `"NONE"` | No | Multimodal Cache | Unique asset identifier. |
| `media_type` | `String (Enum)`| `"TEXT_ONLY"`, `"IMAGE"`, `"VOICE"`, `"DOCUMENT"` | No | Multimodal Cache | Discriminator for media type payload. |
| `sha256_hash` | `String` | 64-char hex string | No | Multimodal Cache | Cryptographic hash of raw asset content. |
| `has_media` | `Boolean` | `True` / `False` | No | System | Discriminator flag for non-text attachments. |
| `image_summary` | `String` | Text description | No | `ImageContext` | Natural language summary of visual content. |
| `image_category` | `String` | `"PAYMENT_RECEIPT"`, `"DOCUMENT"`, etc. | No | `ImageContext` | Inferred category of image asset. |
| `ocr_extracted_text` | `String` | Markdown string | No | `ImageContext` | Full text extracted from image via OCR. |
| `image_risk_score` | `Float` | $0.0 \le r \le 1.0$ | No | `ImageContext` | Calculated risk/scam likelihood score. |
| `voice_transcript` | `String` | Text transcript | No | `VoiceContext` | Speech-to-text decoded transcript of voice note. |
| `voice_duration_seconds`| `Float` | $\ge 0.0$ | No | `VoiceContext` | Audio duration in seconds. |
| `acoustic_tone` | `String (Enum)`| `"CALM"`, `"URGENT"`, `"SHOUTING"`, `"NEUTRAL"` | No | `VoiceContext` | Acoustic emotion tone detected in voice note. |
| `voice_urgency_score` | `Float` | $0.0 \le u \le 1.0$ | No | `VoiceContext` | Speech-derived urgency score. |

---

## 6. `HistoryContext` Model

The `HistoryContext` encapsulates recent message events, historical conversation logs, and past interactions.

### Data Source Mapping
Primary: `message_history.csv` (`history_id`, `user_id`, `peer_id`, `message_count`, `last_interaction_timestamp`)
Secondary: `message_events.csv` (`event_id`, `message_id`, `event_type`, `event_timestamp`)

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `historical_message_count`| `Int` | $\ge 0$ | No | `message_history.csv` | Total historical messages exchanged between sender & receiver. |
| `last_interaction_timestamp`| `Int` | Epoch milliseconds | No | `message_history.csv` | Epoch timestamp of previous message exchange. |
| `days_since_last_interaction`| `Float` | $\ge 0.0$ | No | Computed | Elapsed time in days since last interaction. |
| `recent_event_types` | `List[String]`| List of strings (`"DELIVERED"`, `"READ"`, `"CLICKED"`) | No | `message_events.csv` | Event logs registered for previous messages in thread within last 24h. |
| `historical_similar_message_count`| `Int` | $\ge 0$ | No | Computed | Count of messages from sender with matching intent/category in past 30 days. |

---

## 7. `NotificationContext` Model

The `NotificationContext` encapsulates historical delivery, open, and response behaviors for notification traffic.

### Data Source Mapping
Primary: `daily_notification_summary.csv` (`summary_id`, `user_id`, `date`, `total_notifications_sent`, `notifications_opened`, `avg_response_time_seconds`)

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `user_daily_notification_volume`| `Int` | $\ge 0$ | No | `daily_notification_summary.csv` | Total notifications delivered to user on current calendar date. |
| `historical_open_rate` | `Float` | $0.0 \le o \le 1.0$ | No | `daily_notification_summary.csv` | Historic percentage of notifications opened by target user. |
| `historical_avg_response_seconds`| `Float` | $\ge 0.0$ | No | `daily_notification_summary.csv` | Average latency in seconds for user to respond to notifications. |
| `daily_notification_cap` | `Int` | Default `50` | No | System | User-configured max daily notification threshold. |

---

## 8. `RelationshipContext` Model

The `RelationshipContext` models relational ties, commercial engagement histories, and group authority dynamics.

### Data Source Mapping
Primary: `user_business_history.csv` (`history_id`, `user_id`, `business_id`, `total_orders`, `total_spend`, `last_order_timestamp`, `relationship_tier`)

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `relationship_type` | `String (Enum)`| `"PEER_TO_PEER"`, `"CUSTOMER_BUSINESS"`, `"GROUP_MEMBER"`, `"UNKNOWN"` | No | System | Top-level relationship classification. |
| `customer_total_orders` | `Int` | $\ge 0$ | No | `user_business_history.csv` | Total commercial purchases made by user with business. |
| `customer_total_spend` | `Float` | $\ge 0.0$ | No | `user_business_history.csv` | Cumulative monetary transaction value with business. |
| `commercial_tier` | `String (Enum)`| `"VIP"`, `"REGULAR"`, `"NEW"`, `"NON_CUSTOMER"` | No | `user_business_history.csv` | Customer tier mapping based on historical volume. |
| `is_contacts_saved` | `Boolean` | `True` / `False` | No | Computed | Flag indicating mutual address book saving. |

---

## 9. `ConversationContext` Model

The `ConversationContext` encapsulates current thread state, message burst counts, and active participant metrics.

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `conversation_id` | `String` | Thread ID | No | System | Unique thread identifier (DM pair ID or Group ID). |
| `is_group_chat` | `Boolean` | `True` / `False` | No | System | Thread mode flag. |
| `active_participant_count`| `Int` | $\ge 1$ | No | System | Count of active users sending messages in thread in past 1 hour. |
| `burst_message_count` | `Int` | $\ge 1$ | No | System | Number of consecutive messages sent by current sender in past 5 minutes. |
| `thread_cadence` | `String (Enum)`| `"FAST_REALTIME"`, `"EPISODIC"`, `"DORMANT"` | No | Computed | Inferred conversation pace based on recent inter-message latency. |

---

## 10. `BehaviourContext` Model

The `BehaviourContext` encapsulates aggregate statistical patterns of user activity and message generation habits.

### Field Specifications

| Field Name | Type | Allowed Values / Constraints | Nullable | Source | Description |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `sender_avg_daily_messages`| `Float` | $\ge 0.0$ | No | Computed | Mean number of messages generated daily by sender across all chats. |
| `sender_forward_ratio` | `Float` | $0.0 \le f \le 1.0$ | No | Computed | Proportion of sender's historical messages that are forwarded content. |
| `receiver_quiet_hours_active`| `Boolean` | `True` / `False` | No | Computed | Indicates if message timestamp falls into receiver's typical sleep/quiet window. |
