"""Optional cross-encoder reranking stage.

When ``NM_RERANKER=1`` and the ``sentence-transformers`` CrossEncoder is
available, retrieved candidates are re-scored with
``BAAI/bge-reranker-base`` for a final precision pass. Falls back silently
to RRF order when the model is unavailable — graceful degradation by design.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from nutrimentor.retrieval.schema import Chunk

if TYPE_CHECKING:  # pragma: no cover
    pass

RERANKER_MODEL = os.getenv("NM_RERANKER_MODEL", "BAAI/bge-reranker-base")


class Reranker:
    """Wraps a CrossEncoder; disabled state is a valid, quiet mode."""

    def __init__(self, enabled: bool | None = None) -> None:
        self.enabled = (
            os.getenv("NM_RERANKER", "0").lower() in ("1", "true", "yes")
            if enabled is None
            else enabled
        )
        self._model = None
        if self.enabled:
            self._try_load()

    def _try_load(self) -> None:
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(RERANKER_MODEL, max_length=512)
            print(f"[reranker] loaded {RERANKER_MODEL}")
        except Exception as exc:
            print(f"[reranker] unavailable ({exc}); using RRF order")
            self.enabled = False
            self._model = None

    @property
    def ready(self) -> bool:
        return self.enabled and self._model is not None

    def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        """Re-sort chunks by cross-encoder score; keep RRF score as tiebreak."""
        if not self.ready or not chunks:
            return chunks[:top_k]
        pairs = [(query, c.text[:1500]) for c in chunks]
        try:
            scores = self._model.predict(pairs)
        except Exception:
            return chunks[:top_k]
        for c, s in zip(chunks, scores, strict=False):
            c.scores["rerank"] = float(s)
        reranked = sorted(chunks, key=lambda c: c.scores.get("rerank", 0.0), reverse=True)
        return reranked[:top_k]
