"""Abstract Retrieval Interface Ports for Domain and Application Layers."""

from abc import ABC, abstractmethod
from typing import List, Sequence

from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import (
    EvidenceBundle,
    EvidenceItem,
    RetrievalCandidate,
    StructuredQuery,
)
from router.domain.entities.history import HistoricalMessage


class IQueryBuilder(ABC):
    """Abstract Interface for Query Building and Expansion."""

    @abstractmethod
    def build_query(self, context: MessageContext) -> StructuredQuery:
        """Build structured query from incoming MessageContext."""
        ...


class IBM25Service(ABC):
    """Abstract Interface for Sparse BM25 Keyword Retrieval."""

    @abstractmethod
    def index_messages(self, messages: Sequence[HistoricalMessage]) -> None:
        """Build/update inverted index from historical message corpus."""
        ...

    @abstractmethod
    def search(self, query: StructuredQuery, top_k: int = 100) -> List[RetrievalCandidate]:
        """Perform sparse keyword search and return top_k candidates."""
        ...


class IEmbeddingService(ABC):
    """Abstract Interface for Dense Vector Generation and Vector Search."""

    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generate 384-dimensional L2-normalized vector embedding."""
        ...

    @abstractmethod
    def index_vectors(self, messages: Sequence[HistoricalMessage]) -> None:
        """Build/update FAISS vector index with document embeddings."""
        ...

    @abstractmethod
    def search(self, query_vector: List[float], top_k: int = 100) -> List[RetrievalCandidate]:
        """Perform dense nearest-neighbor similarity search."""
        ...


class IHybridRetriever(ABC):
    """Abstract Interface for Hybrid Reciprocal Rank Fusion (RRF)."""

    @abstractmethod
    def fuse_results(
        self,
        bm25_candidates: List[RetrievalCandidate],
        dense_candidates: List[RetrievalCandidate],
        query: StructuredQuery,
    ) -> List[RetrievalCandidate]:
        """Fuse sparse and dense candidates using RRF and dynamic weighting."""
        ...


class IReranker(ABC):
    """Abstract Interface for Multi-Factor Candidate Re-ranking."""

    @abstractmethod
    def rerank(
        self, candidates: List[RetrievalCandidate], context: MessageContext
    ) -> List[RetrievalCandidate]:
        """Re-rank candidate pool using Cross-Encoder and Multi-Factor scoring."""
        ...


class IEvidenceValidator(ABC):
    """Abstract Interface for Evidence Validation Pipeline."""

    @abstractmethod
    def validate_candidates(
        self, candidates: List[RetrievalCandidate], context: MessageContext
    ) -> List[RetrievalCandidate]:
        """Execute 5 validation gates on candidate pool."""
        ...


class IEvidenceAssembler(ABC):
    """Abstract Interface for Evidence Bundle Assembly."""

    @abstractmethod
    def assemble_bundle(
        self, validated_candidates: List[RetrievalCandidate], context: MessageContext
    ) -> EvidenceBundle:
        """Assemble immutable EvidenceBundle from validated candidates."""
        ...


class IRetrievalEngine(ABC):
    """Abstract Facade Interface for 10-Stage Retrieval Pipeline."""

    @abstractmethod
    def retrieve_evidence(self, context: MessageContext) -> EvidenceBundle:
        """Execute 10-stage hybrid retrieval pipeline and return EvidenceBundle."""
        ...


class IEmbeddingCache(ABC):
    """Abstract Interface for Embedding Cache Tiers."""

    @abstractmethod
    def get_query_embedding(self, query_text: str) -> List[float] | None:
        """Get cached query vector."""
        ...

    @abstractmethod
    def put_query_embedding(self, query_text: str, vector: List[float]) -> None:
        """Put query vector into LRU cache."""
        ...


class IRetrievalCache(ABC):
    """Abstract Interface for EvidenceBundle Retrieval Cache."""

    @abstractmethod
    def get_bundle(self, cache_key: str) -> EvidenceBundle | None:
        """Get cached EvidenceBundle."""
        ...

    @abstractmethod
    def put_bundle(self, cache_key: str, bundle: EvidenceBundle, ttl_seconds: int = 300) -> None:
        """Put EvidenceBundle into retrieval cache with TTL."""
        ...
