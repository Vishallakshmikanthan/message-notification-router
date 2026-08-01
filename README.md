# WhatsApp Message Notification Router

Production-Grade AI System Foundation built with Clean Architecture, Domain-Driven Design (DDD), FastAPI, Pydantic v2, and Python 3.12+.

---

## 🏛️ System Architecture

This repository follows **Clean Architecture (Ports & Adapters)** and **Domain-Driven Design (DDD)**:

- `src/router/domain`: Enterprise Domain Entities, Value Objects, Domain Exceptions, and Abstract Ports.
- `src/router/application`: Application Use Cases, DTOs, and Service Interfaces.
- `src/router/infrastructure`: Technical implementations (PostgreSQL, Redis, Gemini/Vertex AI, Qdrant, Meta Webhook integration).
- `src/router/presentation`: FastAPI endpoints, Webhook controllers, and custom Middleware.
- `src/router/core`: Cross-cutting concerns (Pydantic Settings, Structlog, Error Codes, Constants, Base Exceptions).

---

## 🚀 Quickstart

### Environment Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies via `uv` or `pip`:
   ```bash
   uv pip install -e ".[dev]"
   ```

3. Run static verification:
   ```bash
   ruff check src tests
   mypy src
   ```

4. Run tests:
   ```bash
   pytest
   ```

5. Launch Local Dev Server:
   ```bash
   python -m router.main
   ```
