"""Evidence Domain Entities as specified in evidence_models.md and query_builder.md."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from router.domain.entities.history import HistoricalMessage


@dataclass(frozen=True)
class EvidenceItem:
    """Encapsulates a single historical interaction record retrieved from historical indices."""

    message_id: str
    similarity_score: float  # [0.00, 1.00]
    behaviour_match: float  # [-1.00, 1.00]
    sender_match: float  # [0.00, 1.00]
    business_match: float  # [0.00, 1.00]
    group_match: float  # [0.00, 1.00]
    recency_days: float  # >= 0.0
    importance_weight: float  # [0.40, 1.20]
    trust_score: float  # [0.00, 1.00]
    reason_retrieved: str  # Taxonomic retrieval code
    source_dataset: str = "message_history.csv"  # e.g., message_history.csv
    historical_action_taken: str = "none"  # replied, dismissed, opened, reported, muted, none
    raw_text: str = ""
    created_at_iso: str = ""


@dataclass(frozen=True)
class EvidenceBundle:
    """Aggregates validated EvidenceItem objects for an incoming message into a single payload."""

    query_message_id: str
    user_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    retrieval_confidence: float = 0.0  # [0.00, 1.00]
    evidence_count: int = 0  # 0 to 10
    primary_reason: str = "NO_HISTORICAL_EVIDENCE"
    items: List[EvidenceItem] = field(default_factory=list)
    coverage_score: float = 0.0  # [0.00, 1.00]
    has_conflicting_evidence: bool = False


@dataclass(frozen=True)
class StructuredQuery:
    """Structured query specification built by QueryBuilder for sparse and dense retrieval."""

    user_id: str
    query_text: str
    sparse_terms: List[str] = field(default_factory=list)
    dense_vector: List[float] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    boost_factors: Dict[str, float] = field(default_factory=dict)
    expansion_tokens: List[str] = field(default_factory=list)
    has_numeric_sequence: bool = False
    has_url_domain: bool = False
    domain_mismatch: bool = False


@dataclass
class RetrievalCandidate:
    """Intermediate candidate representation during retrieval pipeline stages."""

    message_id: str
    historical_message: Optional[HistoricalMessage] = None
    bm25_score: float = 0.0
    dense_score: float = 0.0
    rrf_score: float = 0.0
    bm25_rank: Optional[int] = None
    dense_rank: Optional[int] = None
    cross_encoder_score: float = 0.0
    behaviour_score: float = 0.0
    recency_score: float = 0.0
    relationship_score: float = 0.0
    trust_score: float = 0.0
    importance_score: float = 0.0
    final_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
