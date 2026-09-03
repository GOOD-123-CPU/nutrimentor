"""Hybrid retriever: dense (FAISS/BGE) + sparse (BM25/jieba) + RRF fusion.

Why hybrid? Dense vectors capture semantic similarity but miss exact terms
(如 "维生素D3" vs "维D"); BM25 nails keyword matches but misses paraphrase.
Reciprocal Rank Fusion (RRF) merges both rankings robustly without tuning
score scales:

    RRF(d) = Σ_engines  1 / (rrf_k + rank_engine(d))     (rrf_k = 60)

Curated teaching docs receive a small rank bonus so teacher-authored
material surfaces alongside paper abstracts.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from nutrimentor.config import (
    CURATED_PRIORITY,
    HYBRID_CANDIDATES,
    MODEL_DIR,
    RETRIEVAL_K,
    VECTOR_DIR,
    embedding_device,
)
from nutrimentor.retrieval.schema import Chunk

BM25_FILE = "bm25.pkl"
CHUNKS_FILE = "chunks.json"
RRF_K = 60


class HybridRetriever:
    """Loads both indexes and fuses their rankings per query."""

    def __init__(self) -> None:
        self._faiss: Any = None
        self._bm25: Any = None
        self._records: list[dict[str, str]] = []
        self._jieba = None

    # ------------------------------------------------------------------
    def load(self) -> bool:
        vdir = Path(VECTOR_DIR)
        if not (vdir / "index.faiss").exists():
            print(f"[retriever] FAISS index missing at {vdir}. Run ingest first.")
            return False

        from langchain_community.embeddings import HuggingFaceBgeEmbeddings
        from langchain_community.vectorstores import FAISS

        model_path = str(MODEL_DIR) if MODEL_DIR.exists() else None
        if model_path is None:
            print("[retriever] embedding model not found locally; "
                  "set NM_EMBEDDING_MODEL_ID to a HuggingFace id instead.")
            return False

        device = embedding_device()
        print(f"[retriever] loading embeddings (device={device}) ...")
        embeddings = HuggingFaceBgeEmbeddings(
            model_name=model_path,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
        self._faiss = FAISS.load_local(
            str(vdir), embeddings, allow_dangerous_deserialization=True
        )

        bm25_path = vdir / BM25_FILE
        chunks_path = vdir / CHUNKS_FILE
        if bm25_path.exists() and chunks_path.exists():
            with open(bm25_path, "rb") as f:
                self._bm25 = pickle.load(f)
            with open(chunks_path, encoding="utf-8") as f:
                self._records = json.load(f)
            import jieba

            jieba.setLogLevel(60)  # silence init spam
            self._jieba = jieba
            print(f"[retriever] hybrid mode: FAISS + BM25 ({len(self._records)} docs)")
        else:
            self._bm25 = None
            print("[retriever] dense-only mode (BM25 index not found; run ingest)")

        return True

    @property
    def ready(self) -> bool:
        return self._faiss is not None

    # ------------------------------------------------------------------
    def _dense_search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Returns (record_index, similarity) pairs."""
        hits = self._faiss.similarity_search_with_score(query, k=k)
        out = []
        for doc, score in hits:
            idx = self._index_of(doc)
            if idx is not None:
                # FAISS L2 for normalised vectors: smaller is closer.
                sim = 1.0 / (1.0 + max(float(score), 0.0))
                out.append((idx, sim))
        return out

    def _sparse_search(self, query: str, k: int) -> list[tuple[int, float]]:
        if self._bm25 is None or self._jieba is None:
            return []
        # Query expansion: append domain synonym variants before scoring
        from nutrimentor.retrieval.query_expansion import tokenize_for_bm25

        tokens = tokenize_for_bm25(query, self._jieba)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(i, float(scores[i])) for i in ranked if scores[i] > 0]

    def _index_of(self, doc: Any) -> int | None:
        """Map a FAISS doc back to its record index via source+title match."""
        src = doc.metadata.get("source", "")
        title = doc.metadata.get("title", "")
        text_head = doc.page_content[:120]
        for i, rec in enumerate(self._records):
            if rec.get("source") == src or rec.get("title") == title:
                return i
            if rec.get("text", "")[:120] == text_head:
                return i
        return None

    # ------------------------------------------------------------------
    def retrieve(self, query: str) -> tuple[list[Chunk], float]:
        """Hybrid retrieve + fuse. Returns (chunks, best_score)."""
        pool = HYBRID_CANDIDATES
        dense = self._dense_search(query, pool)
        sparse = self._sparse_search(query, pool)

        # RRF fusion
        fused: dict[int, float] = {}
        per_engine: dict[int, dict[str, float]] = {}
        for engine_name, ranking in (("dense", dense), ("bm25", sparse)):
            for rank, (idx, raw) in enumerate(ranking, start=1):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)
                per_engine.setdefault(idx, {})[engine_name] = raw

        # Curated docs bonus: shift them up within equal-score groups by
        # inflating RRF slightly (bounded, not dominant).
        for idx in list(fused):
            if self._records[idx].get("doc_type") == "curated_doc":
                fused[idx] *= 1.0 + 0.08 * CURATED_PRIORITY

        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:RETRIEVAL_K]
        best = ranked[0][1] if ranked else 0.0

        chunks = []
        for idx, score in ranked:
            rec = self._records[idx]
            chunks.append(
                Chunk(
                    text=rec["text"],
                    doc_type=rec.get("doc_type", ""),
                    title=rec.get("title", ""),
                    pmid=rec.get("pmid", ""),
                    source=rec.get("source", ""),
                    authors=rec.get("authors", ""),
                    journal=rec.get("journal", ""),
                    year=rec.get("year", ""),
                    abstract=rec.get("abstract", ""),
                    score=score,
                    scores=per_engine.get(idx, {}),
                )
            )
        return chunks, best
