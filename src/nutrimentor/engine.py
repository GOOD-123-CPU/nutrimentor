"""NutriMentor tutoring engine.

One hybrid retriever + one LLM client power three personas. Adds, on top of
the original project:

* hybrid retrieval with RRF fusion (dense + BM25) + query expansion
* optional cross-encoder reranking (NM_RERANKER=1)
* relevance thresholding (say "not in corpus" instead of hallucinating)
* SQLite-persisted multi-turn conversation memory
* streaming (token-by-token) and non-streaming answer paths
* structured source metadata for frontend reference cards
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from nutrimentor.config import (
    FINAL_TOP_K,
    RELEVANCE_THRESHOLD,
)
from nutrimentor.llm.client import make_client
from nutrimentor.prompts import (
    BASE_RULES,
    BASE_RULES_EN,
    GREETINGS,
    HISTORY_BLOCK,
    NO_DOCS,
    PERSONA_PROMPTS,
    SIMPLE_GREETINGS,
)
from nutrimentor.retrieval.hybrid import HybridRetriever
from nutrimentor.retrieval.schema import Chunk

VALID_PERSONAS = ("student", "teacher", "researcher")


class MentorEngine:
    """Facade combining retrieval, memory and LLM for one persona.

    v2: SQLite session persistence (survives restarts) + optional
    cross-encoder reranking stage.
    """

    def __init__(self, persona: str = "teacher") -> None:
        if persona not in VALID_PERSONAS:
            raise ValueError(f"Unknown persona {persona!r}; expected one of {VALID_PERSONAS}")
        self.persona = persona
        self.retriever = HybridRetriever()
        self.retriever_ready = self.retriever.load()
        from nutrimentor.retrieval.reranker import Reranker

        self.reranker = Reranker()
        self.llm = make_client()
        from nutrimentor.sessions import get_store

        self.store = get_store()

    # ------------------------------------------------------------------
    # Session management (persisted)
    # ------------------------------------------------------------------
    def get_session(self, session_id: str | None) -> str:
        return self.store.ensure_session(session_id, self.persona)

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------
    def _build_context(self, chunks: list[Chunk]) -> str:
        parts = []
        for i, c in enumerate(chunks, 1):
            label = f"学术文献 - PMID: {c.pmid}" if c.pmid else f"科普文章 - {c.title[:50]}"
            parts.append(f"【文献{i} · {label}】\n标题: {c.title}\n内容: {c.text}")
        return "\n\n".join(parts)

    def _render_prompt(self, question: str, context: str, history: str) -> str:
        template = PERSONA_PROMPTS[self.persona]
        if self.persona == "researcher":
            return template.format(
                base_rules_en=BASE_RULES_EN,
                history_block_en=HISTORY_BLOCK.format(history=history) if history else "",
                context=context,
                question=question,
            )
        return template.format(
            base_rules=BASE_RULES,
            history_block=HISTORY_BLOCK.format(history=history) if history else "",
            context=context,
            question=question,
        )

    # ------------------------------------------------------------------
    # Greeting / no-docs short-circuits
    # ------------------------------------------------------------------
    def _is_greeting(self, text: str) -> bool:
        t = text.strip().lower()
        return len(t) <= 10 and any(g in t for g in SIMPLE_GREETINGS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ask(
        self,
        question: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Non-streaming answer. Returns result/sources/session_id/citations."""
        question = question.strip()
        sid = self.get_session(session_id)

        if self._is_greeting(question):
            return {
                "result": GREETINGS[self.persona],
                "sources": [],
                "session_id": sid,
                "citations": "",
            }

        if not self.retriever_ready:
            return {
                "result": NO_DOCS[self.persona],
                "sources": [],
                "session_id": sid,
                "citations": "",
            }

        chunks, best_score = self.retriever.retrieve(question)

        # Relevance gate: fused RRF score below threshold → refuse gracefully
        if not chunks or chunks[0].score < RELEVANCE_THRESHOLD:
            return {
                "result": NO_DOCS[self.persona],
                "sources": [],
                "session_id": sid,
                "citations": "",
            }

        # Optional cross-encoder reranking (no-op when disabled)
        selected = self.reranker.rerank(question, chunks, top_k=FINAL_TOP_K)
        context = self._build_context(selected)
        prompt = self._render_prompt(
            question, context, self.store.history_text(sid)
        )

        answer = self.llm.invoke(prompt)
        self.store.append_turn(sid, self.persona, question, answer)

        return {
            "result": answer,
            "sources": [c.to_public_dict() for c in selected],
            "session_id": sid,
            "citations": self._citation_list(selected),
        }

    def ask_stream(
        self,
        question: str,
        session_id: str | None = None,
    ) -> Generator[str, None, None]:
        """Yields SSE-formatted events: sources first, then answer deltas."""
        import json as _json

        question = question.strip()
        sid = self.get_session(session_id)

        def evt(event: str, data: Any) -> str:
            return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        if self._is_greeting(question):
            yield evt("sources", [])
            yield evt("delta", GREETINGS[self.persona])
            yield evt("done", {"session_id": sid})
            return

        if not self.retriever_ready:
            yield evt("sources", [])
            yield evt("delta", NO_DOCS[self.persona])
            yield evt("done", {"session_id": sid})
            return

        chunks, _ = self.retriever.retrieve(question)
        if not chunks or chunks[0].score < RELEVANCE_THRESHOLD:
            yield evt("sources", [])
            yield evt("delta", NO_DOCS[self.persona])
            yield evt("done", {"session_id": sid})
            return

        selected = self.reranker.rerank(question, chunks, top_k=FINAL_TOP_K)
        yield evt("sources", [c.to_public_dict() for c in selected])

        context = self._build_context(selected)
        prompt = self._render_prompt(
            question, context, self.store.history_text(sid)
        )

        collected = []
        for delta in self.llm.stream(prompt):
            collected.append(delta)
            yield evt("delta", delta)

        full = "".join(collected)
        self.store.append_turn(sid, self.persona, question, full)
        yield evt("done", {"session_id": sid, "citations": self._citation_list(selected)})

    @staticmethod
    def _citation_list(chunks: list[Chunk]) -> str:
        lines = ["参考文献:"]
        for i, c in enumerate(chunks, 1):
            src = f"PMID: {c.pmid}" if c.pmid else (c.source or c.title[:40])
            lines.append(f"[文献{i}] {c.title} ({src})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level singletons (one retriever shared across personas)
# ---------------------------------------------------------------------------
_engines: dict[str, MentorEngine] = {}


def get_engine(persona: str) -> MentorEngine | None:
    """Get or lazily create the engine for a persona. None on failure."""
    if persona not in VALID_PERSONAS:
        return None
    if persona not in _engines:
        try:
            _engines[persona] = MentorEngine(persona=persona)
        except Exception as exc:
            print(f"[engine:{persona}] init failed: {exc}")
            _engines[persona] = None  # type: ignore[assignment]
    return _engines[persona]
