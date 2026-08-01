"""Dense Embedding Retrieval Service and FAISS Vector Engine implementation matching embedding_retrieval.md."""

import json
import logging
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from router.domain.entities.evidence import RetrievalCandidate
from router.domain.entities.history import HistoricalMessage
from router.domain.ports.retrieval_ports import IEmbeddingCache, IEmbeddingService

logger = logging.getLogger(__name__)

# Try importing FAISS if available; otherwise use NumPy VectorIndex fallback
try:
    import faiss

    HAS_FAISS = True
except ImportError:
    faiss = None
    HAS_FAISS = False
    logger.info("FAISS library not installed. Using NumPy-accelerated VectorIndex fallback.")

# Try importing sentence_transformers if available; otherwise use deterministic encoder
try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    SentenceTransformer = None
    HAS_SENTENCE_TRANSFORMERS = False
    logger.info("SentenceTransformers not installed. Using L2-normalized deterministic vector encoder fallback.")


class FAISSIndexWrapper:
    """Wrapper managing FAISS vector index (or NumPy-accelerated fallback)."""

    def __init__(self, dimension: int = 384, index_type: str = "HNSW") -> None:
        """Initialize FAISS vector index wrapper.

        Args:
            dimension: Vector dimension (384 for all-MiniLM-L6-v2).
            index_type: Index type 'HNSW' or 'FlatIP'.
        """
        self.dimension = dimension
        self.index_type = index_type
        self._mapping: Dict[int, str] = {}  # int_id -> message_id
        self._rev_mapping: Dict[str, int] = {}  # message_id -> int_id
        self._next_id = 0

        if HAS_FAISS:
            if index_type == "HNSW":
                # IndexHNSWFlat(dimension, M=32, metric=faiss.METRIC_INNER_PRODUCT)
                self.index = faiss.IndexHNSWFlat(dimension, 32, faiss.METRIC_INNER_PRODUCT)
                self.index.hnsw.efConstruction = 200
                self.index.hnsw.efSearch = 64
            else:
                self.index = faiss.IndexFlatIP(dimension)
        else:
            self.index = None
            self._vectors: List[np.ndarray] = []

    def add_vectors(self, message_ids: List[str], vectors: np.ndarray) -> None:
        """Add normalized vectors and message IDs to the index."""
        num_vecs = len(message_ids)
        if num_vecs == 0:
            return

        for msg_id in message_ids:
            if msg_id not in self._rev_mapping:
                self._mapping[self._next_id] = msg_id
                self._rev_mapping[msg_id] = self._next_id
                self._next_id += 1

        if HAS_FAISS:
            self.index.add(vectors.astype(np.float32))
        else:
            for i in range(num_vecs):
                self._vectors.append(vectors[i].astype(np.float32))

    def search(self, query_vector: np.ndarray, top_k: int = 100) -> List[Tuple[str, float]]:
        """Search top_k nearest neighbors by inner product (cosine similarity)."""
        if self.ntotal == 0:
            return []

        q_vec = query_vector.astype(np.float32).reshape(1, -1)

        if HAS_FAISS:
            scores, indices = self.index.search(q_vec, min(top_k, self.ntotal))
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx in self._mapping:
                    results.append((self._mapping[idx], float(score)))
            return results
        else:
            matrix = np.vstack(self._vectors)  # (N, d)
            scores = np.dot(matrix, q_vec.squeeze(0))  # (N,)
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in top_indices:
                msg_id = self._mapping[int(idx)]
                results.append((msg_id, float(scores[idx])))
            return results

    @property
    def ntotal(self) -> int:
        """Total vectors in index."""
        if HAS_FAISS:
            return self.index.ntotal
        return len(self._vectors)

    def save_mapping(self, filepath: str) -> None:
        """Save integer-to-message_id mapping to JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self._mapping, f, indent=2)

    def load_mapping(self, filepath: str) -> None:
        """Load integer-to-message_id mapping from JSON file."""
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._mapping = {int(k): v for k, v in data.items()}
                self._rev_mapping = {v: int(k) for k, v in data.items()}
                self._next_id = max(self._mapping.keys(), default=-1) + 1


class EmbeddingService(IEmbeddingService):
    """Dense Embedding Service providing sentence transformer inference and FAISS retrieval."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        embedding_cache: Optional[IEmbeddingCache] = None,
        dimension: int = 384,
    ) -> None:
        """Initialize EmbeddingService.

        Args:
            model_name: Transformer model name.
            embedding_cache: Optional EmbeddingCache tier.
            dimension: Dense vector dimension (default 384).
        """
        self._model_name = model_name
        self._embedding_cache = embedding_cache
        self.dimension = dimension

        if HAS_SENTENCE_TRANSFORMERS:
            self._model = SentenceTransformer(model_name)
        else:
            self._model = None

        self._faiss_index = FAISSIndexWrapper(dimension=dimension, index_type="HNSW")
        self._corpus: Dict[str, HistoricalMessage] = {}
        logger.info("EmbeddingService initialized (dimension=%d)", dimension)

    def generate_embedding(self, text: str) -> List[float]:
        """Generate 384-dimensional L2-normalized vector embedding for text string.

        Args:
            text: Text to encode.

        Returns:
            List of 384 floats representing L2-normalized vector.
        """
        if not text:
            return [0.0] * self.dimension

        # Check query LRU cache
        if self._embedding_cache:
            cached = self._embedding_cache.get_query_embedding(text)
            if cached is not None:
                return cached

        if self._model is not None:
            vec = self._model.encode(text, normalize_embeddings=True)
            vector_list = [float(x) for x in vec]
        else:
            # Deterministic fallback encoder producing L2-normalized float vector
            vec = np.zeros(self.dimension, dtype=np.float32)
            words = text.lower().split()
            for w in words:
                h = hash(w)
                idx = abs(h) % self.dimension
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vector_list = [float(x) for x in vec]

        # Put into cache
        if self._embedding_cache:
            self._embedding_cache.put_query_embedding(text, vector_list)

        return vector_list

    def index_vectors(self, messages: Sequence[HistoricalMessage]) -> None:
        """Build/update FAISS vector index for collection of historical messages.

        Args:
            messages: HistoricalMessage entities.
        """
        message_ids: List[str] = []
        vectors_list: List[np.ndarray] = []

        for msg in messages:
            self._corpus[msg.message_id] = msg

            # Composite text document: Text | Sender | Business | Group
            composite_text = f"{msg.message_text} sender:{msg.sender_id}"
            if msg.business_id:
                composite_text += f" business:{msg.business_id}"
            if msg.group_id:
                composite_text += f" group:{msg.group_id}"

            vec = self.generate_embedding(composite_text)
            message_ids.append(msg.message_id)
            vectors_list.append(np.array(vec, dtype=np.float32))

            if self._embedding_cache:
                self._embedding_cache.put_document_embedding(msg.message_id, vec)

        if vectors_list:
            matrix = np.vstack(vectors_list)
            self._faiss_index.add_vectors(message_ids, matrix)

    def search(self, query_vector: List[float], top_k: int = 100) -> List[RetrievalCandidate]:
        """Perform dense vector search against indexed FAISS corpus.

        Args:
            query_vector: 384-d L2-normalized float vector.
            top_k: Number of candidates to return.

        Returns:
            List of RetrievalCandidate objects sorted by dense score.
        """
        if len(query_vector) != self.dimension or self._faiss_index.ntotal == 0:
            return []

        q_arr = np.array(query_vector, dtype=np.float32)
        results = self._faiss_index.search(q_arr, top_k=top_k)

        candidates: List[RetrievalCandidate] = []
        for msg_id, raw_score in results:
            # Sigmoid clipping to ensure [0.0, 1.0] range
            dense_score = float(max(0.0, raw_score))
            msg = self._corpus.get(msg_id)
            candidates.append(
                RetrievalCandidate(
                    message_id=msg_id,
                    historical_message=msg,
                    dense_score=dense_score,
                )
            )

        return candidates
