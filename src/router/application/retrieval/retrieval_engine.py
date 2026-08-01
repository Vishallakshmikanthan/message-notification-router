"""RetrievalEngine main facade implementing 10-Stage Pipeline as specified in retrieval_engine.md."""

import logging
import time
from typing import Optional, Sequence

from router.application.retrieval.bm25_service import BM25Service
from router.application.retrieval.embedding_service import EmbeddingService
from router.application.retrieval.evidence_assembler import EvidenceAssembler
from router.application.retrieval.evidence_validator import EvidenceValidator
from router.application.retrieval.hybrid_retriever import HybridRetriever
from router.application.retrieval.query_builder import QueryBuilder
from router.application.retrieval.reranker import Reranker
from router.domain.entities.context import MessageContext
from router.domain.entities.evidence import EvidenceBundle
from router.domain.entities.history import HistoricalMessage
from router.domain.ports.retrieval_ports import (
    IBM25Service,
    IEmbeddingService,
    IEvidenceAssembler,
    IEvidenceValidator,
    IHybridRetriever,
    IQueryBuilder,
    IReranker,
    IRetrievalCache,
    IRetrievalEngine,
)

logger = logging.getLogger(__name__)


class RetrievalEngine(IRetrievalEngine):
    """Facade orchestrating complete 10-stage Hybrid Retrieval & Evidence Engine pipeline."""

    def __init__(
        self,
        query_builder: Optional[IQueryBuilder] = None,
        bm25_service: Optional[IBM25Service] = None,
        embedding_service: Optional[IEmbeddingService] = None,
        hybrid_retriever: Optional[IHybridRetriever] = None,
        reranker: Optional[IReranker] = None,
        validator: Optional[IEvidenceValidator] = None,
        assembler: Optional[IEvidenceAssembler] = None,
        retrieval_cache: Optional[IRetrievalCache] = None,
    ) -> None:
        """Initialize RetrievalEngine component pipeline.

        Args:
            query_builder: QueryBuilder component.
            bm25_service: BM25Service component.
            embedding_service: EmbeddingService component.
            hybrid_retriever: HybridRetriever component.
            reranker: Reranker component.
            validator: EvidenceValidator component.
            assembler: EvidenceAssembler component.
            retrieval_cache: Optional RetrievalCache component.
        """
        self._embedding_service = embedding_service or EmbeddingService()
        self._query_builder = query_builder or QueryBuilder(embedding_service=self._embedding_service)
        self._bm25_service = bm25_service or BM25Service()
        self._hybrid_retriever = hybrid_retriever or HybridRetriever(k=60)
        self._reranker = reranker or Reranker()
        self._validator = validator or EvidenceValidator()
        self._assembler = assembler or EvidenceAssembler()
        self._retrieval_cache = retrieval_cache

        logger.info("RetrievalEngine pipeline fully initialized across all 8 sub-components")

    def index_corpus(self, messages: Sequence[HistoricalMessage]) -> None:
        """Populate BM25 inverted index and FAISS vector index with historical message corpus."""
        logger.info("Indexing historical corpus of %d messages across BM25 and FAISS", len(messages))
        self._bm25_service.index_messages(messages)
        self._embedding_service.index_vectors(messages)

    def retrieve_evidence(self, context: MessageContext) -> EvidenceBundle:
        """Execute complete 10-stage hybrid retrieval pipeline.

        Args:
            context: Master MessageContext.

        Returns:
            Validated immutable EvidenceBundle container.
        """
        start_time = time.perf_counter()
        query_msg_id = context.message_id or context.core_message.message_id or "UNKNOWN_MSG"
        user_id = context.user_id or context.receiver.user_id or "UNKNOWN_USER"
        raw_text = context.message_text or context.core_message.cleaned_text or ""

        # Check Retrieval Cache
        if self._retrieval_cache and hasattr(self._retrieval_cache, "build_cache_key"):
            cache_key = self._retrieval_cache.build_cache_key(query_msg_id, user_id, raw_text)
            cached_bundle = self._retrieval_cache.get_bundle(cache_key)
            if cached_bundle is not None:
                logger.info("Retrieved EvidenceBundle from cache for msg %s", query_msg_id)
                return cached_bundle

        # Stage 1: Incoming Message Context Intake & Stage 2: Multimodal Enrichment
        # Stage 3: Query Builder Construction & Stage 4: Query Expansion
        query = self._query_builder.build_query(context)

        # Stage 5: Parallel Candidate Generation
        # Stage 6: BM25 Sparse Keyword Retrieval
        bm25_candidates = self._bm25_service.search(query, top_k=100)

        # Stage 7: Dense Vector FAISS Retrieval
        dense_candidates = []
        if query.dense_vector:
            dense_candidates = self._embedding_service.search(query.dense_vector, top_k=100)

        # Stage 8: Hybrid Rank Fusion (RRF k=60)
        fused_candidates = self._hybrid_retriever.fuse_results(bm25_candidates, dense_candidates, query)

        # Stage 9: Multi-Factor Re-ranking
        reranked_candidates = self._reranker.rerank(fused_candidates, context)

        # Stage 10: Evidence Validation & Bundle Assembly
        validated_candidates = self._validator.validate_candidates(reranked_candidates, context)
        bundle = self._assembler.assemble_bundle(validated_candidates, context)

        # Cache result
        if self._retrieval_cache and hasattr(self._retrieval_cache, "build_cache_key"):
            cache_key = self._retrieval_cache.build_cache_key(query_msg_id, user_id, raw_text)
            self._retrieval_cache.put_bundle(cache_key, bundle)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "Executed 10-stage retrieval pipeline for msg %s in %.2fms (items=%d, confidence=%.2f)",
            query_msg_id,
            latency_ms,
            bundle.evidence_count,
            bundle.retrieval_confidence,
        )

        return bundle
