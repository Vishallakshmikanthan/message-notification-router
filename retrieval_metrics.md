# Retrieval Quality Metrics, Systems Performance & Best Practices Specification

## Overview

This document specifies the quantitative evaluation metrics, performance engineering benchmarks, operational optimization strategies, and industry best practices for the Hybrid Retrieval & Evidence Engine.

---

## 1. Retrieval Quality & Evaluation Metrics Framework

To continuously measure and audit retrieval performance, the engine monitors 7 specialized Information Retrieval (IR) metrics:

```mermaid
flowchart TD
    Sub[Retrieved Evidence Candidates] --> M1[Precision@K & Recall@K]
    Sub --> M2[Evidence & Retrieval Confidence]
    Sub --> M3[Coverage Score]
    Sub --> M4[Quality & Diversity Scores]
    
    M1 --> Dash[IR Quality Benchmark Dashboard]
    M2 --> Dash
    M3 --> Dash
    M4 --> Dash
```

### Metric Definitions & Equations

#### 1. Precision@K (P@K)
Measures the proportion of retrieved evidence items in the top-\(K\) results that are truly relevant historical precedents:

$$\text{Precision}@K = \frac{|\text{Relevant Items} \cap \text{Top-}K \text{ Retrieved Items}|}{K}$$

- Target Benchmark: **Precision@5 \(\ge 0.85\)**

#### 2. Recall@K (R@K)
Measures the fraction of total relevant historical items in the corpus that are successfully retrieved within the top-\(K\) pool:

$$\text{Recall}@K = \frac{|\text{Relevant Items} \cap \text{Top-}K \text{ Retrieved Items}|}{|\text{Total Relevant Items in Corpus}|}$$

- Target Benchmark: **Recall@10 \(\ge 0.90\)**

#### 3. Evidence Confidence (\(\text{Conf}_{\text{evidence}}\))
Aggregates the individual validity and trust scores across the top-\(N\) evidence items in an `EvidenceBundle`:

$$\text{Conf}_{\text{evidence}} = \frac{1}{N} \sum_{i=1}^{N} S_{\text{final}}(i) \cdot S_{\text{trust}}(i)$$

#### 4. Retrieval Confidence (\(\text{Conf}_{\text{retrieval}}\))
Measures system certainty in the overall retrieval output, combining similarity score margin between 1st and 5th candidates with evidence count:

$$\text{Conf}_{\text{retrieval}} = \min\left(1.0, \; S_{\text{final}}(1) \cdot \left(1.0 + \frac{S_{\text{final}}(1) - S_{\text{final}}(5)}{2}\right)\right)$$

#### 5. Coverage Score (\(\text{Score}_{\text{coverage}}\))
Evaluates the proportion of relevant contextual dimensions (out of the 18 core objectives) satisfied by the assembled `EvidenceBundle`:

$$\text{Score}_{\text{coverage}} = \frac{\text{Number of Unique Retrieval Objectives Satisfied}}{18}$$

#### 6. Quality Score (\(\text{Score}_{\text{quality}}\))
Composite metric capturing semantic alignment, behavioral precision, and domain trust:

$$\text{Score}_{\text{quality}} = 0.40 \cdot \text{Precision}@5 + 0.35 \cdot \text{Conf}_{\text{evidence}} + 0.25 \cdot \text{Score}_{\text{coverage}}$$

#### 7. Diversity Score (\(\text{Score}_{\text{diversity}}\))
Measures the non-redundancy of retrieved items using Intra-List Diversity (ILD) based on pairwise vector distance:

$$\text{Score}_{\text{diversity}} = \frac{2}{N(N-1)} \sum_{i=1}^{N-1} \sum_{j=i+1}^{N} \left(1.0 - \text{Sim}_{\text{cosine}}(\mathbf{d}_i, \mathbf{d}_j)\right)$$

---

## 2. Performance Engineering & SLA Specifications

The retrieval engine is designed to operate within ultra-low latency constraints in a production messaging environment.

### Target Latency SLAs

| Pipeline Stage | Target Latency (p50) | Target Latency (p99) | Optimization Mechanism |
|---|---|---|---|
| Query Building & Expansion | < 1.0 ms | < 2.5 ms | In-memory tokenization & taxonomy cache |
| BM25 Sparse Search | < 2.0 ms | < 4.5 ms | Inverted index posting list pruning |
| FAISS Dense Vector Search | < 3.0 ms | < 6.0 ms | HNSW graph search (\(\text{efSearch}=64\)) |
| Hybrid RRF Fusion | < 0.5 ms | < 1.0 ms | Single-pass rank merge array |
| Cross-Encoder Re-ranking | < 5.0 ms | < 9.0 ms | Quantized ONNX cross-encoder model |
| Evidence Validation & Assembly | < 0.5 ms | < 1.0 ms | Vectorized NumPy gate validation |
| **Total End-to-End Pipeline** | **< 12.0 ms** | **< 24.0 ms** | **Parallel Async Execution** |

### Memory & Index Optimization

1. **Quantized Vector Storage**: FAISS vector indices use FP16 or Scalar Quantization (SQ8) to reduce RAM usage by 50% without sacrificing recall accuracy.
2. **Parallel Async Retrieval**: BM25 sparse search and FAISS dense vector search execute concurrently using non-blocking asynchronous event loops.
3. **Multi-Tier Embedding Cache**:
   - Tier 1: In-memory LRU cache storing recent 10,000 query embeddings.
   - Tier 2: Persistent Redis cache for historical message document vectors.

---

## 3. Best Practices & Architecture Evolutions

### Modern Enterprise RAG Design Principles
1. **Never Rely Solely on Dense Embeddings**: Dense embeddings struggle with exact OTPs, transaction numbers, and short codes. Always combine sparse BM25 and dense retrieval via rank fusion.
2. **Decouple Retrieval from Routing**: Retrieval engines must provide objective, verifiable evidence bundles without making downstream notification routing decisions.
3. **Filter Before Re-ranking**: Use metadata constraints (`user_id`, `group_id`, `business_id`) to prune search spaces early, avoiding unnecessary compute over irrelevant candidate pairs.

### Common Retrieval Failure Modes & Mitigations

| Failure Mode | Root Cause | System Mitigation |
|---|---|---|
| **Vocabulary Mismatch** | Query uses different terms than historical texts | Query Expansion + Dense Semantic Search |
| **Out-of-Vocabulary Codes** | Unique order/OTP numbers missed by vector models | High-weight BM25 Sparse Keyword Search |
| **Score Scale Misalignment** | BM25 scores \([0, \infty)\) vs Cosine scores \([0, 1]\) | Reciprocal Rank Fusion (RRF) rank-based merging |
| **Semantic Hallucination** | High vector similarity between unrelated short texts | Multi-Factor Cross-Encoder Re-ranking |
| **Cold-Start User Void** | New user has zero message history | Fall back to business/group domain metadata priors |

### Testing & Quality Assurance Strategy

1. **Unit Tests**: Validate tokenizers, BM25 math formulation, RRF fusion logic, and evidence validation gates.
2. **Integration Tests**: Verify async parallel retrieval across BM25 and FAISS indices under simulated concurrency.
3. **IR Quality Benchmarking**: Automated evaluation suite measuring P@5, R@10, and MAP (Mean Average Precision) against gold-standard annotated benchmark datasets (`sample_messages.csv`).
