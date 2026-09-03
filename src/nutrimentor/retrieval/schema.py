"""Pydantic-free lightweight document model used across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """A retrieved unit of knowledge with source metadata."""

    text: str
    doc_type: str  # paper_row | curated_doc
    title: str = ""
    pmid: str = ""
    source: str = ""
    authors: str = ""
    journal: str = ""
    year: str = ""
    abstract: str = ""
    score: float = 0.0  # fused relevance score
    scores: dict[str, float] = field(default_factory=dict)  # per-engine scores

    @property
    def citation_key(self) -> str:
        return f"PMID:{self.pmid}" if self.pmid else self.title[:40]

    def to_public_dict(self) -> dict[str, Any]:
        """Serialise for API responses (no raw text blobs)."""
        return {
            "title": self.title or "未知文献",
            "pmid": self.pmid,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/" if self.pmid else "",
            "doc_type": self.doc_type,
            "authors": self.authors,
            "journal": self.journal,
            "year": self.year,
            "abstract": self.abstract[:400],
            "score": round(self.score, 4),
        }
