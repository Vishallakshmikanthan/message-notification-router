# Personalization Engine Specification

## 1. Executive Summary & Engine Responsibilities

The **Personalization Engine** dynamically adapts base risk, trust, urgency, and behavioral signals to match the individual preferences, historical feedback, contact favorites, and mute habits of the specific recipient user.

Its primary goal is to compute personalized continuous signals ($0.0 \le S_{pers} \le 1.0$) so that two different users receiving an identical message compute distinct, tailored signal bundles reflecting their unique relationship graphs and preferences.

---

## 2. Personalization Feedback Integration Framework

The engine integrates eleven user-specific historical signals to continuously refine baseline scores:

```
                                 [ User Feedback & Context ]
                                              │
  ┌───────────────────────┬───────────────────┼───────────────────┬───────────────────────┐
  │                       │                   │                   │                       │
  ▼                       ▼                   ▼                   ▼                       ▼
Open/Reply Rates    Mute/Report Logs   Favorites & Ties    Notification Load     Recent Engagement
  │                       │                   │                   │                       │
  └───────────────────────┴───────────────────┼───────────────────┴───────────────────────┘
                                              │
                                              ▼
                             ┌─────────────────────────────────┐
                             │ Personalization Weight Adaptation│
                             └─────────────────────────────────┘
                                              │
                                              ▼
                             ┌─────────────────────────────────┐
                             │ Personalized Signal Modulation  │
                             └─────────────────────────────────┘
```

### 2.1 Score Modulation Formula
For any base score $S_{base}$, the personalized score $S_{pers}$ is calculated using user-specific weight vectors $\mathbf{w}_u$ and exponential recency decay $e^{-\lambda \Delta t}$:

$$S_{pers} = \text{Clamp}_{0.0}^{1.0}\left( S_{base} \cdot \left( 1.0 + \sum_{i} w_{u,i} \cdot f_i \cdot e^{-\lambda \Delta t_i} \right) \right)$$

Where $f_i$ represents feedback flags (e.g. `is_favourite_contact`, `is_muted_chat`, `past_spam_report`).

---

## 3. Personalized Signal Specifications

### 3.1 User Behaviour Signal (`user_behaviour_score`)

- **Purpose**: Aggregates composite user activity state and current engagement readiness.
- **Input Fields**:
  - `MessageContext.behaviour_stats.last_active_timestamp` (`Int`)
  - `MessageContext.behaviour_stats.daily_open_rate` (`Float`)
- **Dependencies**: Behavioral Stats.
- **Formula or Reasoning Logic**:
  $$S_{user\_behav} = 0.5 \cdot \text{daily\_open\_rate} + 0.5 \cdot \exp\left(-\frac{t_{\text{now}} - t_{\text{last\_active}}}{1800}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Immediate readiness of user to consume alerts.
- **Examples**: User actively using app in last 5 minutes $\rightarrow S_{user\_behav} = 0.96$.
- **Edge Cases**: User inactive for 3 days: $S_{user\_behav} = 0.05$.
- **How Uncertainty Affects It**: Sparse logs lower confidence to $0.40$.
- **Future Consumers**: Priority Scorer.

---

### 3.2 User Preferences Signal (`user_preference_alignment`)

- **Purpose**: Measures alignment of incoming message context with explicit user choices (starred contacts, VIP channels, muted categories).
- **Input Fields**:
  - `MessageContext.receiver.favourite_contacts` (`List<String>`)
  - `MessageContext.receiver.muted_conversations` (`List<String>`)
- **Dependencies**: User Profile Store.
- **Formula or Reasoning Logic**:
  $$S_{pref} = \begin{cases} 
  0.0 & \text{if conversation\_id } \in \text{muted\_conversations} \\
  1.0 & \text{if sender\_id } \in \text{favourite\_contacts} \\
  0.5 & \text{otherwise (Neutral Baseline)}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Alignment with explicit user overrides.
- **Examples**: Message from user's starred spouse contact $\rightarrow S_{pref} = 1.0$.
- **Edge Cases**: Message from explicitly muted group chat $\rightarrow S_{pref} = 0.0$.
- **How Uncertainty Affects It**: Unset profile defaults to $0.50$.
- **Future Consumers**: Decision Engine, Alert Router.

---

### 3.3 Relevance Signal (`relevance_score`)

- **Purpose**: Estimates contextual interest and importance of topic/sender to recipient.
- **Input Fields**:
  - `MessageContext.relationship.total_interaction_count` (`Int`)
  - `MessageContext.notification_behaviour.sender_open_rate` (`Float`)
  - `MessageContext.core_message.cleaned_text` (`String`)
- **Dependencies**: Natural Language Topic Modeler, Interaction Engine.
- **Formula or Reasoning Logic**:
  $$S_{rel} = 0.5 \cdot \text{open\_rate} + 0.3 \cdot \min\left(1.0, \frac{\text{interactions}}{50}\right) + 0.2 \cdot S_{pref}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: General personal value and topic relevance.
- **Examples**: Close friend sharing topic matching past interest $\rightarrow S_{rel} = 0.94$.
- **Edge Cases**: Mass marketing broadcast: $S_{rel} = 0.08$.
- **How Uncertainty Affects It**: Low context richness defaults to $0.30$.
- **Future Consumers**: Priority Scorer, Digest Engine.

---

### 3.4 Personal Message Detection Signal (`personal_message_score`)

- **Purpose**: Distinguishes 1-on-1 organic human conversation from automated notifications or group broadcasts.
- **Input Fields**:
  - `MessageContext.conversation.is_group_chat` (`Boolean`)
  - `MessageContext.business.is_business_account` (`Boolean`)
  - `MessageContext.relationship.intimacy_score` (`Float`)
- **Dependencies**: Relationship Context.
- **Formula or Reasoning Logic**:
  $$\text{If } \text{is\_group} \text{ OR } \text{is\_business} \implies 0.0. \quad \text{Else } S_{pers\_msg} = \min\left(1.0, 0.4 + 0.6 \cdot \text{intimacy\_score}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Direct organic human communication.
- **Examples**: Direct chat from sibling asking "How was your day?" $\rightarrow S_{pers\_msg} = 0.95$.
- **Edge Cases**: Automated SMS gateway sending direct text: $S_{pers\_msg} = 0.0$.
- **How Uncertainty Affects It**: Ambiguous intimacy defaults to $0.50$.
- **Future Consumers**: Priority Scorer, Notification Filter.

---

### 3.5 Greeting Detection Signal (`greeting_detection_score`)

- **Purpose**: Identifies low-priority conversational pleasantries ("Hi", "Good morning", "Hey").
- **Input Fields**:
  - `MessageContext.core_message.word_count` (`Int`)
  - `MessageContext.core_message.cleaned_text` (`String`)
- **Dependencies**: NLP Classifier.
- **Formula or Reasoning Logic**:
  $$S_{greeting} = \begin{cases} 
  1.0 & \text{if word\_count } \le 3 \text{ AND text } \in \{\text{"hi"}, \text{"hello"}, \text{"good morning"}, \text{"hey"}\} \\
  0.0 & \text{otherwise}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Presence of isolated polite opener lacking immediate actionable content.
- **Examples**: Single-word message "Good morning!" $\rightarrow S_{greeting} = 1.0$.
- **Edge Cases**: "Hi, your house is on fire!" (Word count $> 3$, contains emergency): $S_{greeting} = 0.0$.
- **How Uncertainty Affects It**: Exact match logic yields high confidence $C = 1.0$.
- **Future Consumers**: Notification Summarizer, Batching Engine.

---

### 3.6 Quiet Hours Signal (`quiet_hours_score`)

- **Purpose**: Measures degree of overlap with recipient's scheduled quiet window.
- **Input Fields**:
  - `MessageContext.temporal_info.hour_of_day` (`Int`)
  - `MessageContext.receiver.quiet_hours_start` (`Int`)
  - `MessageContext.receiver.quiet_hours_end` (`Int`)
- **Dependencies**: Temporal Context Engine.
- **Formula or Reasoning Logic**:
  $$\text{Let } h = \text{hour\_of\_day}. \quad S_{quiet} = \begin{cases} 
  1.0 & \text{if } h \in [\text{start}, \text{end}] \\
  0.0 & \text{otherwise}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Message arrived during recipient's designated do-not-disturb timeframe.
- **Examples**: Message arriving at 1:30 AM when quiet hours are 11:00 PM – 7:00 AM $\rightarrow S_{quiet} = 1.0$.
- **Edge Cases**: Emergency alerts bypass quiet hours restriction downstream.
- **How Uncertainty Affects It**: Unset quiet hours default to $0.0$.
- **Future Consumers**: Delivery Scheduler, Quiet Router.

---

### 3.7 Group Importance Signal (`group_importance_score`)

- **Purpose**: Evaluates personal importance of target group to recipient based on role, mentions, and historical activity.
- **Input Fields**:
  - `MessageContext.group.is_group_chat` (`Boolean`)
  - `MessageContext.group.user_role` (`String`)
  - `MessageContext.receiver.favourite_groups` (`List<String>`)
  - `MessageContext.core_message.contains_user_mention` (`Boolean`)
- **Dependencies**: Group Context Model.
- **Formula or Reasoning Logic**:
  $$\text{If NOT group} \implies 0.0. \quad \text{Else } S_{grp\_imp} = \min\left(1.0, 0.4 \cdot \mathbb{I}_{\text{fav}} + 0.3 \cdot \mathbb{I}_{\text{admin}} + 0.5 \cdot \mathbb{I}_{\text{direct\_mention}}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Priority rating of group message for recipient.
- **Examples**: Direct @mention in user's favorite work project group $\rightarrow S_{grp\_imp} = 1.0$.
- **Edge Cases**: Un-starred casual hobby group with no mentions: $S_{grp\_imp} = 0.15$.
- **How Uncertainty Affects It**: Defaults to baseline $0.20$.
- **Future Consumers**: Group Notification Filter.

---

### 3.8 Media Importance Signal (`media_importance_score`)

- **Purpose**: Evaluates information density and value of attached image, voice note, or document.
- **Input Fields**:
  - `MessageContext.media.has_media` (`Boolean`)
  - `MessageContext.media.media_type` (`String`)
  - `MessageContext.media.ocr_text_length` (`Int`)
  - `MessageContext.media.voice_duration_seconds` (`Float`)
- **Dependencies**: Multimodal Intelligence Layer.
- **Formula or Reasoning Logic**:
  $$\text{If NOT media} \implies 0.0. \quad \text{Else } S_{media\_imp} = \begin{cases} 
  \min(1.0, 0.4 + 0.005 \cdot \text{ocr\_length}) & \text{if document / image} \\
  \min(1.0, 0.3 + 0.01 \cdot \text{duration\_sec}) & \text{if voice note}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Value density of non-text payload.
- **Examples**: Detailed PDF invoice document with rich OCR text $\rightarrow S_{media\_imp} = 0.88$.
- **Edge Cases**: 1-second accidental blank voice note: $S_{media\_imp} = 0.05$.
- **How Uncertainty Affects It**: Multimodal failure sets $S_{media\_imp} = 0.10, C = 0.20$.
- **Future Consumers**: Multimodal Priority Scorer.

---

### 3.9 Conversation Importance Signal (`conversation_importance_score`)

- **Purpose**: Measures contextual priority of active ongoing conversation thread.
- **Input Fields**:
  - `MessageContext.conversation.messages_last_24h` (`Int`)
  - `MessageContext.conversation.active_participants_count` (`Int`)
  - `MessageContext.conversation.thread_staleness_hours` (`Float`)
- **Dependencies**: Conversation Engine.
- **Formula or Reasoning Logic**:
  $$S_{conv\_imp} = \min\left(1.0, 0.5 \cdot \min\left(1.0, \frac{\text{msgs\_24h}}{30}\right) + 0.5 \cdot \exp\left(-\frac{\text{staleness\_h}}{12}\right)\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Active conversational thread momentum.
- **Examples**: Rapidly active thread with 25 messages in past 2 hours $\rightarrow S_{conv\_imp} = 0.93$.
- **Edge Cases**: Dormant thread inactive for 30 days: $S_{conv\_imp} = 0.02$.
- **How Uncertainty Affects It**: Thread history gap defaults score to $0.20$.
- **Future Consumers**: Thread Aggregator.
