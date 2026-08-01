# Trust & Relationship Engine Specification

## 1. Executive Summary & Engine Responsibilities

The **Trust Engine** quantifies social closeness, account authenticity, relational strength, structural group safety, and historical reliability between the sender, recipient, and group context.

Its primary goal is to compute interpretable, continuous trust and relationship signals ($0.0 \le S_{trust} \le 1.0$) to guarantee that communications from trusted entities are recognized while unverified entities are appropriately scoped.

---

## 2. Trust & Relationship Signal Specifications

### 2.1 Business Trust Score (`business_trust_score`)

- **Purpose**: Evaluates official verification, brand authenticity, and commercial reputation of business accounts.
- **Input Fields**:
  - `MessageContext.business.is_business_account` (`Boolean`)
  - `MessageContext.business.is_official_verified` (`Boolean`)
  - `MessageContext.business.verification_level` (`String`)
  - `MessageContext.business.spam_report_rate` (`Float`)
- **Dependencies**: `BusinessContext`.
- **Formula or Reasoning Logic**:
  $$S_{biz\_trust} = \begin{cases} 
  0.0 & \text{if NOT business\_account} \\
  1.0 & \text{if official\_verified = true AND spam\_rate < 0.01} \\
  \max\left(0.1, 0.6 \cdot \mathbb{I}_{\text{standard\_biz}} - 2.0 \cdot \text{spam\_rate}\right) & \text{otherwise}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Authenticity and enterprise reliability index.
- **Examples**: Official WhatsApp verified green badge Meta business account $\rightarrow S_{biz\_trust} = 1.0$.
- **Edge Cases**: Fake business account posing as bank with high spam reports $\rightarrow S_{biz\_trust} = 0.05$.
- **How Uncertainty Affects It**: Unverified metadata defaults score to baseline $0.30$.
- **Future Consumers**: Business Router, Commercial Filter.

---

### 2.2 Relationship Score / Strength (`relationship_score`)

- **Purpose**: Quantifies social intimacy, mutual communication frequency, and relational tie strength between sender and recipient.
- **Input Fields**:
  - `MessageContext.relationship.relationship_type` (`String`)
  - `MessageContext.relationship.total_interaction_count` (`Int`)
  - `MessageContext.relationship.reciprocity_ratio` (`Float`)
- **Dependencies**: `RelationshipContext`.
- **Formula or Reasoning Logic**:
  $$S_{rel} = w_{\text{type}} \cdot 0.5 + 0.3 \cdot \min\left(1.0, \frac{\text{interaction\_count}}{100}\right) + 0.2 \cdot \left(1.0 - 2.0 \cdot |0.5 - \text{reciprocity}|\right)$$
  Where $w_{\text{type}} \in \{ \text{SPOUSE}: 1.0, \text{FAMILY}: 0.85, \text{FRIEND}: 0.70, \text{WORK}: 0.60, \text{UNKNOWN}: 0.10 \}$.
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Strength of personal bond and mutual engagement.
- **Examples**: Spouse with 1,000+ past interactions and $0.48$ reciprocity $\rightarrow S_{rel} = 0.99$.
- **Edge Cases**: One-sided fan messaging a public figure (reciprocity $\approx 0.0$): $S_{rel} = 0.15$.
- **How Uncertainty Affects It**: New contacts default to $w_{\text{type}}$ baseline.
- **Future Consumers**: Personalization Engine, Priority Ranking.

---

### 2.3 Known Contact Score (`known_contact_score`)

- **Purpose**: Evaluates contact book integration, mutual contact overlap, and account longevity.
- **Input Fields**:
  - `MessageContext.sender.is_in_contacts` (`Boolean`)
  - `MessageContext.sender.contact_save_duration_days` (`Int`)
  - `MessageContext.relationship.mutual_contacts_count` (`Int`)
- **Dependencies**: Contact Book Sync.
- **Formula or Reasoning Logic**:
  $$S_{known} = \begin{cases} 
  0.0 & \text{if is\_in\_contacts = false} \\
  \min\left(1.0, 0.6 + 0.2 \cdot \min\left(1.0, \frac{\text{duration\_days}}{365}\right) + 0.2 \cdot \min\left(1.0, \frac{\text{mutual}}{5}\right)\right) & \text{if is\_in\_contacts = true}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Verified presence and depth in local phone address book.
- **Examples**: Friend saved in address book for 3 years with 12 mutual contacts $\rightarrow S_{known} = 1.0$.
- **Edge Cases**: Unsaved number: $S_{known} = 0.0$.
- **How Uncertainty Affects It**: Missing contact book permissions lowers confidence to $0.0$.
- **Future Consumers**: Trust Engine, Safety Filter.

---

### 2.4 Group Reliability Score (`group_reliability_score`)

- **Purpose**: Measures structural integrity, admin verification, and spam-free history of a group workspace.
- **Input Fields**:
  - `MessageContext.group.is_group_chat` (`Boolean`)
  - `MessageContext.group.is_announcement_group` (`Boolean`)
  - `MessageContext.group.spam_report_count` (`Int`)
  - `MessageContext.group.admin_count` (`Int`)
- **Dependencies**: Group Context Engine.
- **Formula or Reasoning Logic**:
  $$\text{If NOT group\_chat } \implies 1.0. \quad \text{Else } S_{grp\_rel} = \max\left(0.0, 0.8 - 0.2 \cdot \text{spam\_reports} + 0.2 \cdot \mathbb{I}_{\text{verified\_admins}}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Safety and quality rating of group environment.
- **Examples**: Official company broadcast group managed by verified admins $\rightarrow S_{grp\_rel} = 1.0$.
- **Edge Cases**: Random public link group with multiple spam complaints $\rightarrow S_{grp\_rel} = 0.10$.
- **How Uncertainty Affects It**: Unknown group history defaults to $0.50$.
- **Future Consumers**: Group Notification Manager.

---

### 2.5 Historical Trust Signal (`historical_trust`)

- **Purpose**: Evaluates long-term historical safety record and absence of abuse reports across multi-month windows.
- **Input Fields**:
  - `MessageContext.history.account_age_days` (`Int`)
  - `MessageContext.history.past_spam_reports_count` (`Int`)
  - `MessageContext.history.block_count` (`Int`)
- **Dependencies**: History Context Store.
- **Formula or Reasoning Logic**:
  $$S_{hist\_trust} = \min\left(1.0, \frac{\text{account\_age\_days}}{180}\right) \cdot \exp\left(-0.5 \cdot (\text{spam\_reports} + \text{blocks})\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Multi-month historical reliability index.
- **Examples**: Account active for 2 years with 0 spam reports $\rightarrow S_{hist\_trust} = 1.0$.
- **Edge Cases**: Account created yesterday sending multiple messages $\rightarrow S_{hist\_trust} = 0.05$.
- **How Uncertainty Affects It**: New accounts have low confidence and low historical trust score.
- **Future Consumers**: Risk Engine, Spam Engine.

---

### 2.6 Interaction Strength Signal (`interaction_strength`)

- **Purpose**: Measures the active volume, frequency, and conversational cadence of two-way communication.
- **Input Fields**:
  - `MessageContext.relationship.messages_last_30_days` (`Int`)
  - `MessageContext.relationship.average_response_time_seconds` (`Float`)
- **Dependencies**: History & Relationship Engine.
- **Formula or Reasoning Logic**:
  $$S_{interact} = 0.6 \cdot \min\left(1.0, \frac{\text{msgs\_30d}}{50}\right) + 0.4 \cdot \exp\left(-\frac{\text{avg\_resp\_sec}}{86400}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Active ongoing conversation velocity.
- **Examples**: Active contact with 120 messages in last 30 days and 5-minute avg response time $\rightarrow S_{interact} = 0.98$.
- **Edge Cases**: Contact not messaged in 2 years: $S_{interact} = 0.02$.
- **How Uncertainty Affects It**: Sparse history defaults to $0.10$.
- **Future Consumers**: Personalization Engine, Priority Scorer.
