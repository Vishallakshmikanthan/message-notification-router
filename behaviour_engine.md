# Behavioral Engine Specification

## 1. Executive Summary & Engine Responsibilities

The **Behavioral Engine** models user interaction habits, notification intake load, reading speed, response velocity, dismiss/ignore propensities, and temporal activity patterns.

Its primary goal is to compute continuous behavioral signals ($0.0 \le S_{behaviour} \le 1.0$) that capture how the user naturally consumes notifications, preventing alert fatigue and respecting user focus boundaries.

---

## 2. Behavioral Modeling Framework

The engine maintains statistical interaction state across five dimensions:
1. **Notification Intake Load**: Real-time track of incoming alert density per hour/day.
2. **Engagement Velocity**: Historical response times for specific senders, groups, and categories.
3. **Rejection Dynamics**: Propensity to swipe away or ignore notifications without opening the app.
4. **Temporal Patterns**: Time-of-day and day-of-week active usage curves.
5. **Entity-Specific Receptivity**: Differential engagement rates between personal contacts, work groups, and business accounts.

---

## 3. Behavioral Signal Specifications

### 3.1 Notification Fatigue Signal (`notification_fatigue`)

- **Purpose**: Quantifies user alert overload and current notification pressure.
- **Input Fields**:
  - `MessageContext.notification_behaviour.notifications_last_1_hour` (`Int`)
  - `MessageContext.notification_behaviour.notifications_last_24_hours` (`Int`)
  - `MessageContext.notification_behaviour.user_daily_alert_threshold` (`Int`)
- **Dependencies**: Notification Context Stats.
- **Formula or Reasoning Logic**:
  $$S_{fatigue} = \min\left(1.0, 0.6 \cdot \frac{\text{notifs\_1h}}{10} + 0.4 \cdot \frac{\text{notifs\_24h}}{\text{threshold}}\right)$$
  Where default `threshold` $= 50 \text{ notifications/day}$.
- **Range**: $[0.0, 1.0]$.
- **Meaning**: High score indicates user is experiencing severe alert overload.
- **Examples**:
  - User receives 15 alerts in past 45 mins $\rightarrow S_{fatigue} = 0.95$.
  - User receives 2 alerts in past 4 hours $\rightarrow S_{fatigue} = 0.12$.
- **Edge Cases**: High urgency alerts (e.g. emergency) must bypass fatigue dampening downstream.
- **How Uncertainty Affects It**: If stats missing, fallback to neutral score $0.20$.
- **Future Consumers**: Delivery Rate Limiter, Notification Throttler.

---

### 3.2 Reading Responsiveness Signal (`reading_responsiveness`)

- **Purpose**: Estimates expected speed with which the target user will open and read a message from this sender.
- **Input Fields**:
  - `MessageContext.notification_behaviour.sender_open_rate` (`Float`)
  - `MessageContext.notification_behaviour.median_open_latency_seconds` (`Float`)
- **Dependencies**: Historical Engagement Logs.
- **Formula or Reasoning Logic**:
  $$S_{read\_resp} = 0.6 \cdot \text{open\_rate} + 0.4 \cdot \exp\left(-\frac{\text{median\_open\_sec}}{3600}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Propensity and speed of opening message.
- **Examples**: Historical open rate $95\%$ with median open latency of 30 seconds $\rightarrow S_{read\_resp} = 0.98$.
- **Edge Cases**: Senders never opened (open rate $0\%$): $S_{read\_resp} = 0.0$.
- **How Uncertainty Affects It**: Low sample count ($< 5$ messages) drops confidence $C \le 0.40$.
- **Future Consumers**: Personalization Engine, Priority Ranking.

---

### 3.3 Reply Velocity Signal (`reply_velocity`)

- **Purpose**: Measures user's historical propensity to reply to this sender and average response speed.
- **Input Fields**:
  - `MessageContext.notification_behaviour.sender_reply_rate` (`Float`)
  - `MessageContext.notification_behaviour.median_reply_latency_seconds` (`Float`)
- **Dependencies**: Interaction History Store.
- **Formula or Reasoning Logic**:
  $$S_{reply\_vel} = 0.7 \cdot \text{reply\_rate} + 0.3 \cdot \exp\left(-\frac{\text{median\_reply\_sec}}{14400}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: High score indicates recipient regularly and quickly replies to sender.
- **Examples**: Spouse reply rate $90\%$, median latency 2 minutes $\rightarrow S_{reply\_vel} = 0.97$.
- **Edge Cases**: Broadcast channel (one-way communication): $S_{reply\_vel} = 0.0$.
- **How Uncertainty Affects It**: Sparse history defaults to $0.10$.
- **Future Consumers**: Priority Engine, Interaction Model.

---

### 3.4 Dismiss Propensity Signal (`dismiss_propensity`)

- **Purpose**: Predicts probability of recipient swiping away alert without opening thread.
- **Input Fields**:
  - `MessageContext.notification_behaviour.sender_dismiss_rate` (`Float`)
  - `MessageContext.notification_behaviour.category_dismiss_rate` (`Float`)
- **Dependencies**: Notification Event Logs (`message_events.csv`).
- **Formula or Reasoning Logic**:
  $$S_{dismiss} = 0.6 \cdot \text{sender\_dismiss\_rate} + 0.4 \cdot \text{category\_dismiss\_rate}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Likelihood of active notification rejection.
- **Examples**: User swiped away 8 out of last 10 promo alerts from this brand $\rightarrow S_{dismiss} = 0.82$.
- **Edge Cases**: First message from sender: Uses global category dismiss rate baseline ($0.15$).
- **How Uncertainty Affects It**: Missing event logs reduce confidence to $0.30$.
- **Future Consumers**: Notification Filter, Mute Suggestion Engine.

---

### 3.5 Ignore Propensity Signal (`ignore_propensity`)

- **Purpose**: Predicts probability of user leaving message unread indefinitely.
- **Input Fields**:
  - `MessageContext.notification_behaviour.unread_ratio_for_sender` (`Float`)
  - `MessageContext.history.days_since_last_read` (`Int`)
- **Dependencies**: History Engine.
- **Formula or Reasoning Logic**:
  $$S_{ignore} = \min\left(1.0, 0.7 \cdot \text{unread\_ratio} + 0.3 \cdot \min\left(1.0, \frac{\text{days\_unread}}{30}\right)\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Passive rejection propensity.
- **Examples**: Contact with 15 unread messages over past 60 days $\rightarrow S_{ignore} = 0.94$.
- **Edge Cases**: Highly active chat thread: $S_{ignore} = 0.01$.
- **How Uncertainty Affects It**: Defaults to baseline $0.10$.
- **Future Consumers**: Batching Engine, Quiet Delivery.

---

### 3.6 Time-of-Day Behavioral Affinity Signal (`time_of_day_affinity`)

- **Purpose**: Measures alignment of current hour with user's active historical response window.
- **Input Fields**:
  - `MessageContext.temporal_info.hour_of_day` (`Int`)
  - `MessageContext.behaviour_stats.hourly_activity_distribution` (`List<Float>`)
- **Dependencies**: Temporal Profiler.
- **Formula or Reasoning Logic**:
  $$S_{tod\_affinity} = \text{hourly\_activity\_distribution}[h] \quad \text{where } h \in [0, 23]$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: User's natural phone activity level during current hour.
- **Examples**: Message arriving at 2:00 PM during peak active hours $\rightarrow S_{tod\_affinity} = 0.92$.
- **Edge Cases**: Message arriving at 3:30 AM during deep sleep window $\rightarrow S_{tod\_affinity} = 0.02$.
- **How Uncertainty Affects It**: Uniform distribution fallback ($0.50$) when activity log insufficient.
- **Future Consumers**: Delivery Timing Engine, Quiet Hours Scheduler.

---

### 3.7 Weekend Behavioral Responsiveness Signal (`weekend_responsiveness`)

- **Purpose**: Evaluates willingness to engage with alerts during weekend hours (Sat/Sun).
- **Input Fields**:
  - `MessageContext.temporal_info.is_weekend` (`Boolean`)
  - `MessageContext.behaviour_stats.weekend_engagement_ratio` (`Float`)
  - `MessageContext.relationship.is_work_related` (`Boolean`)
- **Dependencies**: Behavioral Stats.
- **Formula or Reasoning Logic**:
  $$\text{If NOT is\_weekend} \implies 1.0. \quad \text{Else } S_{wknd\_resp} = \begin{cases} 
  \text{weekend\_engagement\_ratio} \cdot 0.3 & \text{if is\_work\_related = true} \\
  \text{weekend\_engagement\_ratio} \cdot 1.0 & \text{otherwise}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Receptivity to notification types on weekends.
- **Examples**: Work message sent on Sunday to user who disconnects on weekends $\rightarrow S_{wknd\_resp} = 0.08$.
- **Edge Cases**: Personal family message on weekend: $S_{wknd\_resp} = 0.95$.
- **How Uncertainty Affects It**: Default $0.50$ score on missing stats.
- **Future Consumers**: Work-Life Balance Router.

---

### 3.8 Group Engagement Signal (`group_engagement`)

- **Purpose**: Quantifies user participation, reading, and response activity within target group.
- **Input Fields**:
  - `MessageContext.group.is_group_chat` (`Boolean`)
  - `MessageContext.group.user_message_count_30d` (`Int`)
  - `MessageContext.group.user_read_rate` (`Float`)
- **Dependencies**: Group Context Engine.
- **Formula or Reasoning Logic**:
  $$\text{If NOT group\_chat} \implies 1.0. \quad \text{Else } S_{grp\_eng} = 0.5 \cdot \text{user\_read\_rate} + 0.5 \cdot \min\left(1.0, \frac{\text{user\_msgs\_30d}}{20}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Level of personal interest and participation in group workspace.
- **Examples**: Active core member of project team group $\rightarrow S_{grp\_eng} = 0.91$.
- **Edge Cases**: Large 500-person broadcast group user never speaks in: $S_{grp\_eng} = 0.05$.
- **How Uncertainty Affects It**: New group membership defaults to $0.30$.
- **Future Consumers**: Group Notification Summarizer.

---

### 3.9 Business Engagement Signal (`business_engagement`)

- **Purpose**: Evaluates user's historical receptivity to commercial and transactional messages.
- **Input Fields**:
  - `MessageContext.business.is_business_account` (`Boolean`)
  - `MessageContext.behaviour_stats.business_open_rate` (`Float`)
  - `MessageContext.behaviour_stats.business_reply_rate` (`Float`)
- **Dependencies**: Business Context Engine.
- **Formula or Reasoning Logic**:
  $$\text{If NOT business\_account} \implies 1.0. \quad \text{Else } S_{biz\_eng} = 0.7 \cdot \text{biz\_open\_rate} + 0.3 \cdot \text{biz\_reply\_rate}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: User willingness to receive commercial updates.
- **Examples**: User who frequently opens order tracking messages $\rightarrow S_{biz\_eng} = 0.88$.
- **Edge Cases**: User who blocks all promotional business chats: $S_{biz\_eng} = 0.02$.
- **How Uncertainty Affects It**: Defaults to category baseline $0.35$.
- **Future Consumers**: Commercial Router.
