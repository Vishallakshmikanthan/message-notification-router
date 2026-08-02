# Master Architecture Specification: Hackathon Submission Strategy

This document details the submission presentation blueprint, README structure, artifact packaging requirements, output CSV validation suite, and submission checklist for the AI-powered WhatsApp Message Notification Router hackathon entry.

---

## 1. Executive Summary & Strategy Philosophy

Winning AI hackathons requires equal excellence in **Architectural Rigor**, **Engineering Execution**, and **Submission Presentation**.

Our submission strategy focuses on:
- **Instant Visual Impact**: High-impact architecture diagrams and crisp evaluation metrics right at the top of the README.
- **Flawless Artifact Integrity**: 100% schema validation on `output.csv` with zero missing values or broken fields.
- **Enterprise-Grade Documentation**: Clean folder hierarchy, zero temporary cache garbage, and reproducible execution commands.

---

## 2. README Structure & Visual Hierarchy

The `README.md` acts as the primary showcase artifact for hackathon judges.

```
┌──────────────────────────────────────────────────────────────────┐
│ 🚀 PROJECT TITLE: AI WhatsApp Message Notification Router        │
│ [Badges: Python 3.11 | Gemini 1.5 | OpenTelemetry | F1: 0.94]     │
├──────────────────────────────────────────────────────────────────┤
│ 1. 🎯 Executive Summary & Problem Statement                      │
│ 2. 🏛️ Master System Architecture Diagram (Mermaid / SVG)         │
│ 3. ⚡ Core Differentiators (Hybrid Rule-LLM, Self-Healing JSON)   │
│ 4. 📊 Benchmark & Evaluation Results (F1, ECE, Latency)          │
│ 5. 🛠️ Quickstart & CLI Execution Guide                            │
│ 6. 📁 Repository & Codebase Directory Structure                  │
│ 7. 🔒 Security, Safety & Privacy Hardening                       │
└──────────────────────────────────────────────────────────────────┘
```

### Key README Sections Detail

1. **Architecture Visual**: Embeds clean Mermaid flowcharts illustrating the 4-tier LLM execution graph, rule engine bypass, and multi-agent verification DAG.
2. **Benchmark Table**: Displays quantitative accuracy, latency (p50/p90/p99), ECE calibration, and token cost metrics proving system performance.
3. **Execution Snippets**: Copies exact, copy-pasteable CLI commands to reproduce evaluation and CSV generation.

---

## 3. Submission Folder & Project Layout

```
message-notification-router/
├── README.md                   # Primary Submission Showcase
├── pyproject.toml              # Locked Dependency & Build Specification
├── ruff.toml / mypy.ini        # Code Quality & Static Analysis Configs
├── docs/                       # Complete Architectural Specifications
│   ├── architecture.md
│   ├── llm_strategy.md
│   ├── prompt_architecture.md
│   ├── agent_architecture.md
│   ├── evaluation_framework.md
│   ├── observability.md
│   ├── performance.md
│   └── deployment.md
├── src/                        # Production Source Code
│   └── router/
│       ├── __init__.py
│       ├── main.py             # Entry point & CLI Runner
│       ├── rules/              # Tier 0 Rule Engine
│       ├── agents/             # Multi-Agent Microservice Nodes
│       ├── prompts/            # Versioned Prompt Templates
│       ├── retrieval/          # Hybrid Vector/BM25 RAG Engine
│       └── validation/         # Self-Healing JSON Parser
├── tests/                      # PyTest Test Suite & Edge Cases
├── eval/                       # Benchmark Harness & Evaluation Scripts
├── submission/                 # Final Submission Package Artifacts
│   ├── output.csv              # Validated Benchmark Routing Output
│   ├── code.zip                # Clean Source Code Archive
│   └── chat_transcript.json    # Agent Conversation & Ideation Log
```

---

## 4. Submission Artifact Packaging Specifications

- **Header Structure**: `message_id,action,message_type,reason,confidence,evidence_message_ids`
- **Action Schema Enforcer**: Values strictly restricted to `notify`, `digest`, `mute`.
- **MessageType Schema Enforcer**: Values strictly restricted to 11 valid categories (`personal`, `urgent`, `event`, `payment`, `business_update`, `promotion`, `greeting`, `forward`, `spam`, `scam`, `unknown`).
- **Confidence Schema Enforcer**: Float value bounded strictly between `0.00` and `1.00`.
- **Evidence Schema Enforcer**: Semicolon-separated message ID list or `none`.
- **Null Value Guard**: Zero empty cells permitted across all rows.


### 2. `code.zip` Packaging Cleanliness Protocol
- **Excluded Patterns**: `.git/`, `__pycache__/`, `.pytest_cache/`, `.venv/`, `.env`, `.DS_Store`, `*.pyc`.
- **Inclusions**: Complete `src/`, `docs/`, `tests/`, `pyproject.toml`, and README artifacts.

### 3. `chat_transcript` Log Preparation
- Formatted as a clean JSONL transcript documenting structural reasoning, prompt design iterations, and architecture design steps.

---

## 5. Submission Quality Assurance Checklist

```mermaid
checklist
    title Pre-Submission Verification Gate
    "output.csv row count matches input dataset exactly" : [x]
    "output.csv column headers match specification" : [x]
    "Zero unhandled exceptions or malformed JSON responses" : [x]
    "Macro F1 evaluation score exceeds target threshold (>=0.90)" : [x]
    "All architecture specification markdown files present in docs/" : [x]
    "code.zip contains zero secrets or virtual environment binaries" : [x]
    "README quickstart commands execute without error" : [x]
```
