# Complete Data Dictionary

## Overview
This data dictionary documents every column across all 13 CSV files in the WhatsApp Message Notification Router dataset, detailing data types, nullability rules, valid value ranges, foreign key constraints, and operational descriptions.

---

## 1. `messages.csv` (Primary Incoming Message Stream)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `message_id` | String | NO | PK | `msg_[0-9]{3}` | Unique identifier for incoming test/inference message. |
| `user_id` | String | NO | FK | Maps to `users.user_id` | Recipient user ID receiving the notification. |
| `conversation_type` | String | NO | None | `personal`, `group`, `business` | Type of WhatsApp conversation channel. |
| `group_id` | String | YES | FK | Maps to `groups.group_id` | Group ID if `conversation_type == 'group'`. Mandatory if group; NULL otherwise. |
| `business_id` | String | YES | FK | Maps to `business_accounts.business_id` | Business account ID if `conversation_type == 'business'`. Mandatory if business; NULL otherwise. |
| `sender_user_id` | String | YES | FK | Maps to `users.user_id` | Sender's user ID if `conversation_type` IN (`personal`, `group`). |
| `created_at` | Timestamp | NO | None | `YYYY-MM-DD HH:MM:SS` | Message arrival timestamp. |
| `message_text` | Text | YES | None | UTF-8, multi-line allowed | Text payload. Empty/NULL for pure voice notes. |
| `media_type` | String | YES | None | `image`, `voice`, or NULL/empty | Attached media category. |
| `media_id` | String | YES | FK | Maps to `images.image_id` or `voice_notes.voice_note_id` | Identifier of attached image or voice note asset. |
| `forwarded_count` | Integer | NO | None | `[0, inf)` | Number of times the message has been forwarded across WhatsApp. |

---

## 2. `users.csv` (Recipient User Profiles)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `user_id` | String | NO | PK | `u_[0-9]{3}` | Unique recipient user identifier. |
| `do_not_disturb_window` | String | NO | None | `HH:MM-HH:MM` (e.g. `22:00-07:00`) | User's preferred quiet hours window. |
| `messages_opened_30d` | Integer | NO | None | `[0, inf)` | Total messages opened by user across all chats in last 30 days. |
| `messages_replied_30d` | Integer | NO | None | `[0, inf)` | Total replies sent by user across all chats in last 30 days. |
| `notifications_dismissed_30d` | Integer | NO | None | `[0, inf)` | Total notifications swiped away/dismissed without opening in 30d. |
| `messages_reported_30d` | Integer | NO | None | `[0, inf)` | Total spam/scam reports filed by user in last 30 days. |

---

## 3. `groups.csv` (Group Metadata)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `group_id` | String | NO | PK | `group_[0-9]{3}` | Unique group chat identifier. |
| `group_name` | String | NO | None | Free text string | Display name of the group. |
| `group_type` | String | NO | None | `family`, `society`, `school_group`, `coworker`, `marketplace`, `friends`, `alumni`, `extended_family` | Categorical classification of the group context. |
| `member_count` | Integer | NO | None | `[2, inf)` | Total number of participants in the group. |
| `admin_count` | Integer | NO | None | `[1, member_count]` | Total number of group administrators. |
| `created_at` | Date | NO | None | `YYYY-MM-DD` | Date the group was created. |
| `messages_30d` | Integer | NO | None | `[0, inf)` | Total message volume in group over the last 30 days. |

---

## 4. `group_members.csv` (User-Group Membership & Settings)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `group_id` | String | NO | PK, FK | Maps to `groups.group_id` | Target group identifier. |
| `user_id` | String | NO | PK, FK | Maps to `users.user_id` | Target user identifier. |
| `role` | String | NO | None | `admin`, `member` | User's permissions level in this group. |
| `joined_at` | Date | NO | None | `YYYY-MM-DD` | Date the user joined this group. |
| `messages_sent_30d` | Integer | NO | None | `[0, inf)` | Messages sent by user in this group (30d). |
| `messages_read_30d` | Integer | NO | None | `[0, inf)` | Messages read by user in this group (30d). |
| `replies_sent_30d` | Integer | NO | None | `[0, inf)` | Direct replies sent by user in this group (30d). |
| `notifications_dismissed_30d` | Integer | NO | None | `[0, inf)` | Group notifications dismissed by user (30d). |
| `group_muted_by_user` | Integer | NO | None | `0` or `1` | Boolean indicator whether user explicitly muted this group. |

---

## 5. `business_accounts.csv` (Business Sender Profiles)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `business_id` | String | NO | PK | `business_[0-9]{3}` | Unique business account identifier. |
| `display_name` | String | NO | None | Free text string | Verified display title of the business. |
| `brand_name` | String | NO | None | Free text string | Commercial brand name. |
| `category` | String | NO | None | `ecommerce_delivery`, `bank`, `fashion`, `ride_booking`, `telecom`, `logistics`, `streaming`, `payments` | Business sector domain. |
| `verified` | Integer | NO | None | `0` or `1` | Meta Green Tick / Official Verification indicator. |
| `official_domain` | String | NO | None | Domain format (e.g. `amazon.in`) | Registered official domain name of the business entity. |
| `domain_used_by_sender` | String | NO | None | Domain format (e.g. `amazonpay-delivery.in`) | Exact domain embedded or used by sender in messages. |
| `account_age_days` | Integer | NO | None | `[0, inf)` | Age of the WhatsApp business account in days. |
| `messages_sent_30d` | Integer | NO | None | `[0, inf)` | Total outbound messages sent by business (30d). |
| `user_reports_30d` | Integer | NO | None | `[0, inf)` | Global spam/scam report count against business in 30d. |
| `domain_used_by_sender_age_days` | Integer | NO | None | `[0, inf)` | Domain registration age of `domain_used_by_sender` in days. |

---

## 6. `user_business_history.csv` (User-Business Interactions)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `user_id` | String | NO | PK, FK | Maps to `users.user_id` | Recipient user identifier. |
| `business_id` | String | NO | PK, FK | Maps to `business_accounts.business_id` | Business account identifier. |
| `why_user_knows_account` | String | NO | None | Free text / Categorical | Relationship origin (e.g. `recent_grocery_delivery`, `active_bank_account`). |
| `last_activity_at` | Timestamp | NO | None | `YYYY-MM-DD HH:MM` | Timestamp of last user activity with this business. |
| `allows_promotions` | Integer | NO | None | `0` or `1` | User promotional consent flag. |
| `promotions_opted_out_at` | Timestamp | YES | None | `YYYY-MM-DD HH:MM` or NULL | Timestamp when user opted out of promotional messages. |
| `activity_count_180d` | Integer | NO | None | `[0, inf)` | Count of transaction activities over last 180 days. |
| `messages_opened_30d` | Integer | NO | None | `[0, inf)` | Messages opened from this business (30d). |
| `messages_dismissed_30d` | Integer | NO | None | `[0, inf)` | Notifications dismissed from this business (30d). |
| `messages_replied_30d` | Integer | NO | None | `[0, inf)` | Replies sent to this business (30d). |
| `last_reply_at` | Timestamp | YES | None | `YYYY-MM-DD HH:MM` or NULL | Timestamp of last user reply to business. |

---

## 7. `message_history.csv` (Historical Message Corpus)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `message_id` | String | NO | PK | `message_[0-9]{4}` | Unique historical message identifier. |
| `user_id` | String | NO | FK | Maps to `users.user_id` | Recipient user identifier. |
| `conversation_type` | String | NO | None | `personal`, `group`, `business` | Channel type. |
| `group_id` | String | YES | FK | Maps to `groups.group_id` | Group ID if group chat. |
| `business_id` | String | YES | FK | Maps to `business_accounts.business_id` | Business ID if business chat. |
| `sender_user_id` | String | YES | FK | Maps to `users.user_id` | Sender user ID if group/personal. |
| `created_at` | Timestamp | NO | None | `YYYY-MM-DD HH:MM:SS` | Arrival timestamp. |
| `message_text` | Text | YES | None | UTF-8, multi-line | Text content of historical message. |
| `media_type` | String | YES | None | `image`, `voice`, or NULL | Media type. |
| `media_id` | String | YES | FK | Maps to `images.image_id` or `voice_notes.voice_note_id` | Media asset ID. |
| `forwarded_count` | Integer | NO | None | `[0, inf)` | Forward count indicator. |

---

## 8. `message_events.csv` (Historical Message Interaction Events)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `user_id` | String | NO | PK, FK | Maps to `users.user_id` | Recipient user ID performing action. |
| `message_id` | String | NO | PK, FK | Maps to `message_history.message_id` | Referenced historical message ID. |
| `message_opened` | Integer | NO | None | `0` or `1` | Whether user opened the message. |
| `message_replied` | Integer | NO | None | `0` or `1` | Whether user replied to the message. |
| `reaction_time_minutes` | Integer | YES | None | `[0, inf)` or NULL | Time in minutes between message arrival and user action. |
| `notification_dismissed` | Integer | NO | None | `0` or `1` | Whether notification was dismissed. |
| `muted_after_message` | Integer | NO | None | `0` or `1` | Whether user muted chat immediately following message. |
| `message_reported` | Integer | NO | None | `0` or `1` | Whether user reported message as spam/scam. |

---

## 9. `images.csv` (Image Media Manifest)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `image_id` | String | NO | PK | `img_[0-9]{3}` | Unique image identifier. |
| `file_path` | String | NO | None | `media/images/img_[0-9]{3}.jpg` | Relative disk path to JPEG image asset. |

---

## 10. `voice_notes.csv` (Audio Media Manifest)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `voice_note_id` | String | NO | PK | `vn_[0-9]{3}` | Unique voice note identifier. |
| `file_path` | String | NO | None | `media/audio/vn_[0-9]{3}.mp3` | Relative disk path to MP3 audio asset. |

---

## 11. `daily_notification_summary.csv` (User Daily Notification Volume)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `user_id` | String | NO | PK, FK | Maps to `users.user_id` | User identifier. |
| `date` | Date | NO | PK | `YYYY-MM-DD` | Date of aggregated metrics. |
| `notifications_sent` | Integer | NO | None | `[0, inf)` | Total notifications pushed to user on date. |
| `notifications_dismissed` | Integer | NO | None | `[0, inf)` | Total notifications dismissed by user on date. |

---

## 12. `sample_messages.csv` (Reference Examples / Gold Standard)

Contains all columns from `messages.csv` PLUS:
- `action`: Allowed values `notify`, `digest`, `mute`
- `message_type`: Allowed values `personal`, `urgent`, `event`, `payment`, `business_update`, `promotion`, `greeting`, `forward`, `spam`, `scam`, `unknown`
- `reason`: Explanation string
- `confidence`: Float `[0.0, 1.0]`
- `evidence_message_ids`: Semicolon-separated historical message IDs or `none`

---

## 13. `output.csv` (Inference Output Template)

| Column Name | Data Type | Nullable? | PK/FK | Constraints / Allowed Values | Description |
|---|---|---|---|---|---|
| `message_id` | String | NO | PK, FK | Maps to `messages.message_id` | Target message identifier. |
| `action` | String | NO | None | `notify`, `digest`, `mute` | Final notification routing decision. |
| `message_type` | String | NO | None | Categorical taxonomy value | Categorical message classification. |
| `reason` | String | NO | None | Human-readable explanation string | Rationale for decision. |
| `confidence` | Float | NO | None | `[0.00, 1.00]` | Model confidence score. |
| `evidence_message_ids` | String | NO | FK | `message_XXXX;message_YYYY` or `none` | Supporting evidence historical message IDs. |
