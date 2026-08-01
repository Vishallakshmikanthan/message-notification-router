# Risk Engine Specification

## 1. Executive Summary & Engine Responsibilities

The **Risk Engine** evaluates safety hazards, scam patterns, financial fraud indicators, spam broadcasts, and unauthorized promotional activity associated with an incoming `MessageContext`.

Its primary goal is to compute continuous, explainable risk signals ($0.0 \le S_{risk} \le 1.0$) to protect the user from malicious content, phishing, and notification spam.

---

## 2. Risk Signal Specifications

### 2.1 Spam Detection Signal (`spam`)

- **Purpose**: Quantifies the probability that the incoming message is an unsolicited bulk spam broadcast.
- **Input Fields**:
  - `MessageContext.core_message.contains_links` (`Boolean`)
  - `MessageContext.core_message.contains_phone_numbers` (`Boolean`)
  - `MessageContext.core_message.char_count` (`Int`)
  - `MessageContext.core_message.is_forwarded` (`Boolean`)
  - `MessageContext.sender.is_in_contacts` (`Boolean`)
  - `MessageContext.history.past_spam_reports_count` (`Int`)
- **Dependencies**: None.
- **Formula or Reasoning Logic**:
  $$S_{spam} = \sigma\left( w_1 \cdot \mathbb{I}_{\text{no\_contact}} + w_2 \cdot \mathbb{I}_{\text{links}} + w_3 \cdot \min(\text{reports}, 5) + w_4 \cdot \mathbb{I}_{\text{fwd}} - b \right)$$
  Where $\sigma(z) = \frac{1}{1 + e^{-z}}$, $w_1 = 1.2$, $w_2 = 0.8$, $w_3 = 1.5$, $w_4 = 0.6$, $b = 1.8$.
- **Range**: $[0.0, 1.0]$ ($0.0 = \text{Clean Message}$, $1.0 = \text{Definite Bulk Spam}$).
- **Meaning**:
  - $0.0 - 0.2$: Legitimate organic conversation.
  - $0.2 - 0.6$: Mild promotional or unknown marketing message.
  - $0.6 - 1.0$: High-confidence unsolicited spam broadcast.
- **Examples**:
  - *Example 1*: Unknown sender sending "Click here to win a free gift card http://bit.ly/xyz" $\rightarrow S_{spam} = 0.94$.
  - *Example 2*: Saved contact sending "Hey, are you free for lunch today?" $\rightarrow S_{spam} = 0.02$.
- **Edge Cases**:
  - Known contact sending a forwarded link (e.g., news article): $S_{spam}$ suppressed due to $S_{\text{contact}} = \text{true}$.
- **How Uncertainty Affects It**: If contact status is unknown or history missing, confidence defaults to $0.50$ and score falls back to baseline $0.35$.
- **Future Consumers**: Priority Scorer, Spam Filter, Security Auditor.

---

### 2.2 Scam Detection Signal (`scam`)

- **Purpose**: Identifies social engineering, phishing, prize scams, and deceptive identity impersonation attempts.
- **Input Fields**:
  - `MessageContext.core_message.cleaned_text` (`String`)
  - `MessageContext.sender.is_verified_business` (`Boolean`)
  - `MessageContext.sender.is_in_contacts` (`Boolean`)
  - `MessageContext.media.ocr_extracted_text` (`String`)
- **Dependencies**: Multimodal Layer (OCR Text).
- **Formula or Reasoning Logic**:
  Evaluates keyword/regex vector matches for urgency hooks ("account suspended", "verify OTP immediately", "lottery winner") combined with unverified sender status:
  $$S_{scam} = \min\left(1.0, \mathbb{I}_{\text{unverified}} \cdot \left(0.4 \cdot \text{ScamKeywords} + 0.5 \cdot \mathbb{I}_{\text{credential\_request}}\right)\right)$$
- **Range**: $[0.0, 1.0]$ ($0.0 = \text{Safe}$, $1.0 = \text{Active Phishing / Scam}$).
- **Meaning**: High score indicates dangerous social engineering designed to defraud the user.
- **Examples**:
  - *Example 1*: "Your bank account is blocked. Share your 6-digit code to unblock" from unsaved number $\rightarrow S_{scam} = 0.98$.
- **Edge Cases**:
  - Official bank sending legitimate transaction alert containing "OTP": Verified business status reduces $S_{scam}$ to $0.05$.
- **How Uncertainty Affects It**: High text ambiguity reduces confidence $C_{scam}$; high scam score forces security review.
- **Future Consumers**: Security Router, Phishing Alert Engine.

---

### 2.3 Fraud Indicators Signal (`fraud_indicator`)

- **Purpose**: Detects illicit financial requests, gift card scams, money transfer coercion, or unauthorized payment demands.
- **Input Fields**:
  - `MessageContext.core_message.cleaned_text` (`String`)
  - `MessageContext.media.extracted_amounts` (`List<Float>`)
  - `MessageContext.relationship.total_interaction_count` (`Int`)
- **Dependencies**: OCR / Natural Language Entity Parser.
- **Formula or Reasoning Logic**:
  $$S_{fraud} = \begin{cases} 
  0.0 & \text{if } \text{interaction\_count} > 50 \text{ AND } \text{is\_contact} = \text{true} \\
  \sigma(1.5 \cdot \mathbb{I}_{\text{payment\_request}} + 1.2 \cdot \mathbb{I}_{\text{crypto/giftcard}} - 1.0) & \text{otherwise}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Likelihood of financial theft or extortion attempt.
- **Examples**:
  - Unknown number asking "Send $500 via wire transfer immediately" $\rightarrow S_{fraud} = 0.92$.
- **Edge Cases**: Friends splitting a restaurant bill ("Pay me back $25 on Venmo"): High interaction count zeroes out fraud risk.
- **How Uncertainty Affects It**: OCR failure degrades confidence; defaults to conservative $0.20$ score.
- **Future Consumers**: Fraud Monitor, Financial Safety Guard.

---

### 2.4 Business Trust Risk Signal (`business_trust_risk`)

- **Purpose**: Measures the risk level associated with unverified or deceptive business profiles.
- **Input Fields**:
  - `MessageContext.business.is_business_account` (`Boolean`)
  - `MessageContext.business.is_official_verified` (`Boolean`)
  - `MessageContext.business.spam_report_rate` (`Float`)
- **Dependencies**: `BusinessContext`.
- **Formula or Reasoning Logic**:
  $$S_{biz\_risk} = \begin{cases} 
  0.0 & \text{if NOT business\_account} \\
  0.05 & \text{if official\_verified} = \text{true} \\
  \min\left(1.0, 0.4 + 1.5 \cdot \text{spam\_report\_rate}\right) & \text{otherwise}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: High score indicates untrusted commercial sender with high spam history.
- **Examples**: Unverified business account sending promo messages $\rightarrow S_{biz\_risk} = 0.70$.
- **Edge Cases**: Newly registered business with no history: Baseline risk $0.40$.
- **How Uncertainty Affects It**: Unverified business data reduces signal confidence to $0.40$.
- **Future Consumers**: Business Commercial Engine, Mute Policy.

---

### 2.5 Forward Chain Risk Signal (`forward_chain_risk`)

- **Purpose**: Evaluates risk from virally forwarded messages across the network.
- **Input Fields**:
  - `MessageContext.core_message.is_forwarded` (`Boolean`)
  - `MessageContext.core_message.forward_count` (`Int`)
  - `MessageContext.core_message.is_frequently_forwarded` (`Boolean`)
- **Dependencies**: Forward tracking pipeline.
- **Formula or Reasoning Logic**:
  $$S_{fwd\_risk} = \min\left(1.0, 0.2 \cdot \mathbb{I}_{\text{forwarded}} + 0.15 \cdot \text{forward\_count} + 0.3 \cdot \mathbb{I}_{\text{frequently\_forwarded}}\right)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Measures misinformation, viral hoax, or fake news distribution risk.
- **Examples**: Message forwarded $> 5$ times ("Share this with 10 contacts to win") $\rightarrow S_{fwd\_risk} = 0.85$.
- **Edge Cases**: Personal message forwarded once between spouses $\rightarrow S_{fwd\_risk} = 0.20$.
- **How Uncertainty Affects It**: Missing forward count defaults to $0.20$ if `is_forwarded` is true.
- **Future Consumers**: Misinformation Filter, Notification Demoter.

---

### 2.6 Unknown Sender Risk Signal (`unknown_sender_risk`)

- **Purpose**: Quantifies baseline exposure risk originating from unsaved or non-reciprocal contacts.
- **Input Fields**:
  - `MessageContext.sender.is_in_contacts` (`Boolean`)
  - `MessageContext.relationship.is_mutual_contact` (`Boolean`)
  - `MessageContext.group.is_group_chat` (`Boolean`)
- **Dependencies**: Contact Book Sync.
- **Formula or Reasoning Logic**:
  $$S_{unk\_risk} = \begin{cases} 
  0.0 & \text{if is\_in\_contacts = true AND is\_mutual = true} \\
  0.25 & \text{if is\_in\_contacts = true AND is\_mutual = false} \\
  0.10 & \text{if is\_group\_chat = true} \\
  0.85 & \text{otherwise (Unknown Direct Sender)}
  \end{cases}$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Degree of caller/sender anonymity.
- **Examples**: Direct message from random phone number $+19998887777 \rightarrow S_{unk\_risk} = 0.85$.
- **Edge Cases**: Unknown sender inside a mutual family group chat: Lowered to $0.10$.
- **How Uncertainty Affects It**: If contact sync is pending, confidence drops to $0.30$.
- **Future Consumers**: Privacy Engine, Direct Message Filter.

---

### 2.7 Visual Scam Risk Signal (`visual_scam_risk`)

- **Purpose**: Evaluates scam risk embedded in image attachments (e.g. fake QR codes, bank screenshots).
- **Input Fields**:
  - `MessageContext.media.has_image` (`Boolean`)
  - `MessageContext.media.ocr_extracted_text` (`String`)
  - `MessageContext.media.detected_qr_codes` (`List<String>`)
- **Dependencies**: Multimodal Image Pipeline & OCR Engine.
- **Formula or Reasoning Logic**:
  $$\text{If } \text{has\_image} = \text{false} \implies 0.0. \quad \text{Else } S_{vis\_scam} = \sigma(1.4 \cdot \mathbb{I}_{\text{QR\_present}} + 1.1 \cdot \mathbb{I}_{\text{OCR\_scam\_text}} - 1.2)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Fraud/phishing hazard present inside visual payload.
- **Examples**: Image containing QR code labeled "Scan to receive payment" $\rightarrow S_{vis\_scam} = 0.91$.
- **Edge Cases**: Meme image containing casual text: $S_{vis\_scam} = 0.02$.
- **How Uncertainty Affects It**: Low OCR confidence propagates to low signal confidence.
- **Future Consumers**: Image Safety Analyzer, Media Filter.

---

### 2.8 Voice Scam Risk Signal (`voice_scam_risk`)

- **Purpose**: Evaluates fraud and voice cloning scam indicators from audio voice note transcripts.
- **Input Fields**:
  - `MessageContext.media.has_voice_note` (`Boolean`)
  - `MessageContext.media.voice_transcript` (`String`)
  - `MessageContext.media.acoustic_stress_score` (`Float`)
- **Dependencies**: Multimodal Voice Pipeline (ASR & Acoustic Analyzer).
- **Formula or Reasoning Logic**:
  $$\text{If } \text{has\_voice} = \text{false} \implies 0.0. \quad \text{Else } S_{voice\_scam} = \sigma(1.3 \cdot \mathbb{I}_{\text{urgency\_voice}} + 0.8 \cdot \text{stress\_score} - 1.1)$$
- **Range**: $[0.0, 1.0]$.
- **Meaning**: Extortion or fake emergency voice note risk.
- **Examples**: Voice note saying "I was arrested, transfer money to this account" from unknown number $\rightarrow S_{voice\_scam} = 0.95$.
- **Edge Cases**: Family voice note laughing: $S_{voice\_scam} = 0.01$.
- **How Uncertainty Affects It**: Low transcript accuracy (noisy audio) reduces confidence $C \le 0.40$.
- **Future Consumers**: Voice Safety Filter, Priority Engine.
