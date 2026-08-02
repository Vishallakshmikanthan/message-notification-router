# Urgency Engine Specification

## 1. Executive Summary & Engine Responsibilities

The **Urgency Engine** measures time criticality, real-world deadlines, health/safety emergencies, financial transactions, and scheduled events associated with an incoming message.

Its primary goal is to produce continuous, explainable urgency signals ($0.0 \le S_{urgency} \le 1.0$) to enable rapid alerting for time-sensitive situations while preventing false alarms.

---

## 2. Urgency Signal Specifications

### 2.1 Emergency Detection Signal (`emergency`)

- **Purpose**: Identifies acute physical danger, accidents, distress calls, or immediate crisis situations.
- **Input Fields**:
  - `MessageContext.core_message.cleaned_text` (`String`)
  - `MessageContext.relationship.relationship_type` (`String`)
  - `MessageContext.media.voice_transcript` (`String`)
- **Dependencies**: Multimodal Voice Pipeline, Relationship Context.
- **Formula or Reasoning Logic**:
  $$S_{emergency} = \min\left(1.0, 0.6 \cdot \mathbb{I}_{\text{emergency\_keywords}} + 0.3 \cdot \mathbb{I}_{\text{immediate\_family}} + 0.3 \cdot \mathbb{I}_{\text{high\_voice\_stress}}\right)$$
  Emergency keywords: "SOS", "help me", "accident", "hospitalized", "911", "call immediately".
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Immediate critical physical or personal distress alert.
- **Examples**:
  - Spouse messaging "In hospital right now, car breakdown on highway, call me!" $\rightarrow S_{emergency} = 0.98$.
  - Friend messaging "That movie was dangerously good!" $\rightarrow S_{emergency} = 0.02$.
- **Edge Cases**: Figurative slang ("I'm dying of laughter"): Contextual NLP filter suppresses false positive.
- **How Uncertainty Affects It**: If sender identity is uncertain, score stays high for safety, but confidence is flagged.
- **Future Consumers**: Emergency Bypass Engine, Immediate Alert Router.

---

### 2.2 Time-Sensitive Event Signal (`time_sensitive_event`)

- **Purpose**: Detects events occurring within a near-term temporal window ($< 2 \text{ hours}$).
- **Input Fields**:
  - `MessageContext.core_message.cleaned_text` (`String`)
  - `MessageContext.temporal_info.timestamp_epoch_ms` (`Int`)
  - `MessageContext.media.extracted_timestamps` (`List<Int>`)
- **Dependencies**: Entity Extractor (Temporal Parser).
- **Formula or Reasoning Logic**:
  $$\Delta t = \frac{t_{\text{event}} - t_{\text{now}}}{3600 \text{ sec}} \implies S_{time\_event} = \begin{cases} 
  1.0 & \text{if } 0 \le \Delta t \le 0.5 \\
  \exp(-0.5 \cdot (\Delta t - 0.5)) & \text{if } 0.5 < \Delta t \le 6.0 \\
  0.05 & \text{if } \Delta t > 6.0 \text{ OR } \Delta t < 0
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Temporal decay curve measuring proximity of an upcoming activity.
- **Examples**: "Flight boarding in 20 minutes at Gate B4" $\rightarrow S_{time\_event} = 0.96$.
- **Edge Cases**: Past events ($\Delta t < 0$): Urgency collapses to $0.05$.
- **How Uncertainty Affects It**: Unparsed time expressions default score to $0.30$.
- **Future Consumers**: Time-Sensitive Alert Scheduler.

---

### 2.3 Payment Urgency Signal (`payment`)

- **Purpose**: Identifies financial transaction alerts, OTPs, bill due dates, and pending money requests.
- **Input Fields**:
  - `MessageContext.core_message.cleaned_text` (`String`)
  - `MessageContext.business.business_category` (`String`)
- **Dependencies**: Entity Extractor.
- **Formula or Reasoning Logic**:
  $$S_{payment} = \max\left( \mathbb{I}_{\text{OTP\_code}} \cdot 1.0, \quad \mathbb{I}_{\text{bill\_overdue}} \cdot 0.85, \quad \mathbb{I}_{\text{payment\_request}} \cdot 0.60 \right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Priority of financial transaction or authentication code.
- **Examples**: "Your bank OTP for $150 transaction is 492019. Valid 5 mins" $\rightarrow S_{payment} = 1.0$.
- **Edge Cases**: Standard promotional discount ("Get 20% off bill"): $S_{payment} = 0.10$.
- **How Uncertainty Affects It**: High entity confidence yields high signal confidence.
- **Future Consumers**: Financial Notification Engine, OTP Fast-Pass.

---

### 2.4 Deadline Urgency Signal (`deadline`)

- **Purpose**: Evaluates task, work assignment, or document submission expiry.
- **Input Fields**:
  - `MessageContext.core_message.cleaned_text` (`String`)
  - `MessageContext.media.extracted_dates` (`List<String>`)
- **Dependencies**: Task Entity Extractor.
- **Formula or Reasoning Logic**:
  $$S_{deadline} = \sigma\left( 2.0 \cdot \mathbb{I}_{\text{today\_deadline}} + 1.2 \cdot \mathbb{I}_{\text{tomorrow\_deadline}} - 0.5 \right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Task expiration proximity.
- **Examples**: "Submit project proposal by 5 PM today sharp" $\rightarrow S_{deadline} = 0.93$.
- **Edge Cases**: Vague deadlines ("Submit when you get a chance"): $S_{deadline} = 0.20$.
- **How Uncertainty Affects It**: Missing time parser lowers confidence to $0.40$.
- **Future Consumers**: Work & Productivity Manager.

---

### 2.5 Meeting Urgency Signal (`meeting`)

- **Purpose**: Detects live conference calls, video meetings, or immediate schedule adjustments.
- **Input Fields**:
  - `MessageContext.core_message.contains_links` (`Boolean`)
  - `MessageContext.core_message.cleaned_text` (`String`)
- **Dependencies**: Meeting URL Matcher (Zoom, Meet, Teams).
- **Formula or Reasoning Logic**:
  $$S_{meeting} = \min\left(1.0, 0.5 \cdot \mathbb{I}_{\text{meeting\_link}} + 0.4 \cdot \mathbb{I}_{\text{starting\_now}} + 0.2 \cdot \mathbb{I}_{\text{schedule\_change}}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Live meeting launch or immediate calendar shift.
- **Examples**: "Starting standup now, join here: https://meet.google.com/abc-def" $\rightarrow S_{meeting} = 0.95$.
- **Edge Cases**: Meeting scheduled for next month: $S_{meeting} = 0.15$.
- **How Uncertainty Affects It**: Link presence provides high confidence $C \ge 0.90$.
- **Future Consumers**: Calendar Integration Engine.

---

### 2.6 Appointment Urgency Signal (`appointment`)

- **Purpose**: Evaluates healthcare, service, delivery, or professional appointment updates.
- **Input Fields**:
  - `MessageContext.business.is_business_account` (`Boolean`)
  - `MessageContext.core_message.cleaned_text` (`String`)
- **Dependencies**: Commercial Entity Engine.
- **Formula or Reasoning Logic**:
  $$S_{appt} = \max\left( \mathbb{I}_{\text{doctor\_appt}} \cdot 0.90, \quad \mathbb{I}_{\text{delivery\_arriving}} \cdot 0.80, \quad \mathbb{I}_{\text{service\_confirmed}} \cdot 0.50 \right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Immediate real-world appointment alert.
- **Examples**: "Your courier package is out for delivery and arriving in 30 mins" $\rightarrow S_{appt} = 0.82$.
- **Edge Cases**: Subscription renewal reminder 30 days away: $S_{appt} = 0.15$.
- **How Uncertainty Affects It**: Standard fallback to $0.20$ score.
- **Future Consumers**: Life & Service Alert Manager.

---

### 2.7 Family Emergency Signal (`family_emergency`)

- **Purpose**: Measures distress calls originating specifically from primary family relations.
- **Input Fields**:
  - `MessageContext.relationship.relationship_type` (`String`)
  - `MessageContext.core_message.cleaned_text` (`String`)
- **Dependencies**: Relationship Context Model.
- **Formula or Reasoning Logic**:
  $$S_{fam\_emerg} = \begin{cases} 
  S_{emergency} \cdot 1.0 & \text{if } \text{relationship\_type} \in \{\text{SPOUSE}, \text{PARENT}, \text{CHILD}\} \\
  S_{emergency} \cdot 0.6 & \text{if } \text{relationship\_type} = \text{EXTENDED\_FAMILY} \\
  0.0 & \text{otherwise}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Urgent distress signal filtered by close kin tie.
- **Examples**: Mother sending "Please call back, your father's test results arrived" $\rightarrow S_{fam\_emerg} = 0.89$.
- **Edge Cases**: Unregistered family member number: Falls back to general `emergency`.
- **How Uncertainty Affects It**: Family graph uncertainty lowers confidence.
- **Future Consumers**: Kinship Safety Manager.

---

### 2.8 Health Emergency Signal (`health_emergency`)

- **Purpose**: Detects acute medical alerts, hospital reports, prescription updates, or wellness emergencies.
- **Input Fields**:
  - `MessageContext.core_message.cleaned_text` (`String`)
  - `MessageContext.business.business_category` (`String`)
- **Dependencies**: Health Category Parser.
- **Formula or Reasoning Logic**:
  $$S_{health\_emerg} = \min\left(1.0, 0.7 \cdot \mathbb{I}_{\text{medical\_keywords}} + 0.3 \cdot \mathbb{I}_{\text{hospital/lab\_sender}}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Medical urgency index.
- **Examples**: "Lab alert: Critical blood glucose result ready for patient" $\rightarrow S_{health\_emerg} = 0.94$.
- **Edge Cases**: General health blog newsletter: $S_{health\_emerg} = 0.05$.
- **How Uncertainty Affects It**: Low confidence drops score to safety baseline.
- **Future Consumers**: Healthcare Alert Router.

---

### 2.9 Critical Announcement Signal (`critical_announcement`)

- **Purpose**: Measures high-priority organizational, workplace, or emergency broadcast notices.
- **Input Fields**:
  - `MessageContext.group.is_group_chat` (`Boolean`)
  - `MessageContext.group.user_role` (`String`)
  - `MessageContext.core_message.cleaned_text` (`String`)
- **Dependencies**: Group Context Model.
- **Formula or Reasoning Logic**:
  $$S_{crit\_ann} = \mathbb{I}_{\text{admin\_sender}} \cdot \sigma(1.5 \cdot \mathbb{I}_{\text{all\_mention}} + 1.2 \cdot \mathbb{I}_{\text{urgent\_keyword}} - 1.0)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: High-level structural announcement from an authoritative sender.
- **Examples**: Company VP messaging @everyone "Office closed today due to severe weather emergency" $\rightarrow S_{crit\_ann} = 0.97$.
- **Edge Cases**: Non-admin sending casual message with @everyone: $S_{crit\_ann} = 0.15$.
- **How Uncertainty Affects It**: Role ambiguity defaults score to $0.30$.
- **Future Consumers**: Group & Organization Alert System.
