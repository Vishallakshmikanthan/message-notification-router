"""Sparse BM25 Keyword Retrieval Service implementation matching bm25.md specification."""

import math
import re
import unicodedata
from collections.abc import Sequence

from router.domain.entities.evidence import RetrievalCandidate, StructuredQuery
from router.domain.entities.history import HistoricalMessage
from router.domain.ports.retrieval_ports import IBM25Service

# Preserved stop-words (negations and urgency tokens MUST NOT be removed)
PRESERVED_STOPWORDS: set[str] = {"not", "no", "don't", "dont", "never", "now", "urgent", "immediately"}

# Generic stop-words to filter
DEFAULT_STOPWORDS: set[str] = {
    "is", "the", "at", "in", "on", "a", "an", "and", "or", "to", "for", "of", "with", "this", "that", "it", "by", "be"
} - PRESERVED_STOPWORDS

FIELD_WEIGHTS: dict[str, float] = {
    "sender_user_id": 3.0,
    "business_id": 3.0,
    "official_domain": 2.5,
    "ocr_text": 1.5,
    "voice_transcript": 1.2,
    "message_text": 1.0,
    "image_caption": 0.8,
    "group_type": 0.5,
}


class BM25Service(IBM25Service):
    """BM25 Sparse Keyword Retrieval Service with multi-field weighting."""

    def __init__(self, k1: float = 1.2, b: float = 0.75, epsilon: float = 0.25) -> None:
        """Initialize BM25 parameters.

        Args:
            k1: Term frequency saturation hyperparameter (1.2).
            b: Document length normalization hyperparameter (0.75).
            epsilon: Negative/low IDF floor value (0.25).
        """
        self._k1 = k1
        self._b = b
        self._epsilon = epsilon

        # Document store and stats
        self._corpus: dict[str, HistoricalMessage] = {}
        self._doc_tokens: dict[str, list[str]] = {}
        self._doc_lengths: dict[str, int] = {}
        self._df: dict[str, int] = {}  # Document frequency of terms
        self._avgdl: float = 0.0
        self._N: int = 0

    def tokenize(self, text: str) -> list[str]:
        """Preprocess and tokenize text following Unicode NFKC and entity preservation rules."""
        if not text:
            return []
        # Unicode Normalization
        text_norm = unicodedata.normalize("NFKC", text).lower()

        # Preserve numeric sequences, currencies, URLs, and words
        raw_tokens = re.findall(r"https?://\S+|\b\d{4,8}\b|\$\d+|\brs\.\s*\d+|\b\w+\b", text_norm)

        tokens: list[str] = []
        for t in raw_tokens:
            if t in DEFAULT_STOPWORDS:
                continue
            tokens.append(t)
        return tokens

    def index_messages(self, messages: Sequence[HistoricalMessage]) -> None:
        """Build/update BM25 inverted index over historical messages.

        Args:
            messages: Collection of HistoricalMessage entities.
        """
        for msg in messages:
            self._corpus[msg.message_id] = msg
            tokens = self.tokenize(msg.message_text)

            # Incorporate sender/business tokens
            if msg.sender_id:
                tokens.append(msg.sender_id.lower())
            if msg.business_id:
                tokens.append(msg.business_id.lower())
            if msg.group_id:
                tokens.append(msg.group_id.lower())

            self._doc_tokens[msg.message_id] = tokens
            self._doc_lengths[msg.message_id] = len(tokens)

        self._N = len(self._doc_tokens)
        if self._N > 0:
            self._avgdl = sum(self._doc_lengths.values()) / float(self._N)

        # Compute document frequencies
        self._df.clear()
        for doc_id, tokens in self._doc_tokens.items():
            unique_terms = set(tokens)
            for term in unique_terms:
                self._df[term] = self._df.get(term, 0) + 1

    def _idf(self, term: str) -> float:
        """Calculate Inverse Document Frequency (IDF) with epsilon floor."""
        n_q = self._df.get(term, 0)
        if n_q == 0:
            return 0.0
        idf_val = math.log((self._N - n_q + 0.5) / (n_q + 0.5) + 1.0)
        return max(self._epsilon, idf_val)

    def search(self, query: StructuredQuery, top_k: int = 100) -> list[RetrievalCandidate]:
        """Perform BM25 search over indexed corpus for query.

        Args:
            query: StructuredQuery specification.
            top_k: Number of top candidates to retrieve.

        Returns:
            Sorted list of RetrievalCandidate instances.
        """
        if self._N == 0:
            return []

        query_terms = set()
        for term in query.sparse_terms:
            query_terms.update(self.tokenize(term))

        candidates: list[RetrievalCandidate] = []

        # Numerical sequence in query for exact numeric boosting
        numeric_matches = re.findall(r"\b\d{4,8}\b", query.query_text)

        for doc_id, msg in self._corpus.items():
            doc_toks = self._doc_tokens[doc_id]
            doc_len = self._doc_lengths[doc_id]

            if doc_len == 0:
                continue

            # Calculate term frequencies
            tf_map: dict[str, int] = {}
            for tok in doc_toks:
                tf_map[tok] = tf_map.get(tok, 0) + 1

            score = 0.0
            for term in query_terms:
                if term not in tf_map:
                    continue
                f = tf_map[term]
                idf = self._idf(term)

                num = f * (self._k1 + 1.0)
                den = f + self._k1 * (1.0 - self._b + self._b * (doc_len / self._avgdl))
                score += idf * (num / den)

            # Field Boosts & Exact Numeric Match Multiplier (4.0x)
            if numeric_matches:
                for num_code in numeric_matches:
                    if num_code in msg.message_text:
                        score *= 4.0
                        break

            # Sender/Business exact filter boost
            sender_filter = query.filters.get("sender_user_id")
            if sender_filter and msg.sender_id == sender_filter:
                score *= FIELD_WEIGHTS["sender_user_id"]

            business_filter = query.filters.get("business_id")
            if business_filter and msg.business_id == business_filter:
                score *= FIELD_WEIGHTS["business_id"]

            if score > 0.0:
                candidates.append(
                    RetrievalCandidate(
                        message_id=doc_id,
                        historical_message=msg,
                        bm25_score=score,
                    )
                )

        # Sort candidates descending by BM25 score
        candidates.sort(key=lambda c: c.bm25_score, reverse=True)
        return candidates[:top_k]
