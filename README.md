# AI-Powered WhatsApp Message Notification Router

> **Production-Grade Foundation & Clean Architecture Implementation (Phase 1)**

The **Message Notification Router** is an intelligent, high-throughput, multi-agent AI system designed to evaluate and route every incoming WhatsApp message into `notify`, `digest`, or `mute`. The system combines personalization profiles, multimodal extractions (OCR/ASR/VLM), historical interaction trajectories, and risk-awareness safety filters.

---

## 🏗️ System Architecture

Built in strict adherence to **Clean Architecture** and **Domain-Driven Design (DDD)** principles:

```
src/router/
├── core/                   # Application Infrastructure Foundation
│   ├── config/             # Pydantic Settings v2 configuration
│   ├── constants/          # System constants & error codes
│   ├── exceptions/         # Root exception hierarchy
│   └── logging/            # Structlog JSON structured logging
├── domain/                 # Pure Business Logic & Models
│   ├── entities/           # User, Group, Business, Media, Message, Context, Signal
│   ├── value_objects/      # MessageId, NotificationAction, MessageType, RiskLevel
│   ├── exceptions/         # Domain-specific validation errors
│   └── ports/              # Abstract interfaces & contracts (Repositories, Services, Agents)
├── infrastructure/         # External Systems & Concrete Implementations
│   ├── storage/            # DataLoader, FileManager, SchemaValidator, QuarantineEngine
│   ├── repositories/       # In-memory thread-safe domain repositories
│   ├── cache/              # Multi-tier LRU/TTL CacheManager
│   ├── memory/             # StringInternPool, IndexManager, ResourceManager
│   └── observability/      # OpenTelemetry & JSON Audit Logger
├── application/            # Orchestration & Workflow Use Cases
│   ├── data/               # DataManager facade & Lookup Services
│   ├── context/            # ContextService & ContextBuilder
│   ├── signals/            # SignalEngine & 7 analytical calculators
│   ├── rules/              # RuleEngine hard-filter safety override
│   ├── agents/             # Micro-Agent topology (Router, Safety, Evidence, Confidence, Classifier)
│   └── decision/           # DecisionEngine & ConfidenceCalibrator
└── main.py                 # FastAPI Application Lifecycle Entry Point
```

---

## ⚙️ Environment Setup & Installation

### 1. Prerequisites
- Python >= 3.12

### 2. Install Dependencies
```bash
pip install -r requirements.txt
# OR using editable package install:
pip install -e .
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

---

## 🧪 Verification & Testing

Execute the automated unit test suite using `pytest`:

```bash
pytest
```

Execute static type checking using `mypy`:
```bash
mypy src/router
```

Execute code style and linting using `ruff`:
```bash
ruff check src/router
```

---

## 🚀 Running the FastAPI Application

Launch the development server:
```bash
python -m router.main
```

Or using `uvicorn`:
```bash
uvicorn router.main:app --reload --port 8000
```
