"""Document ingestion: xlsx/csv paper tables + docx/md curated docs.

Produces both a FAISS vector index and a BM25 lexical index so the
retriever can run hybrid (dense + sparse) search.
"""

from __future__ import annotations

import json
import pickle
import shutil
from pathlib import Path

import pandas as pd
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import FAISS

from nutrimentor.config import (
    DATA_DIR,
    EMBEDDING_MODEL_ID,
    MODEL_DIR,
    VECTOR_DIR,
    embedding_device,
)

COL_ALIASES = {
    "pmid": ["PMID", "pmid"],
    "title": ["Title", "title"],
    "authors": ["Authors", "authors"],
    "journal": ["Journal", "Journal_clean", "Journal Name"],
    "year": ["Year", "year"],
    "abstract": ["Abstract", "abstract"],
    "impact_factor": ["Impact Factor", "ImpactFactor", "IF"],
}

BM25_FILE = "bm25.pkl"
CHUNKS_FILE = "chunks.json"
FAISS_MARKER = "index.faiss"


# ---------------------------------------------------------------------------
# Sample data seeding
# ---------------------------------------------------------------------------
def seed_sample_data(data_dir: Path, assets_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    sample_csv = assets_dir.parent / "sample_papers.csv"
    if sample_csv.exists() and not any(data_dir.glob("*.csv")):
        shutil.copy(sample_csv, data_dir / sample_csv.name)
        print(f"Seeded: {sample_csv.name}")
    sample_md_dir = assets_dir / "sample_articles"
    if sample_md_dir.exists() and not any(data_dir.glob("*.md")):
        for md in sample_md_dir.glob("*.md"):
            shutil.copy(md, data_dir / md.name)
            print(f"Seeded: {md.name}")


# ---------------------------------------------------------------------------
# Table loaders
# ---------------------------------------------------------------------------
def _resolve_col(df: pd.DataFrame, keys: list[str]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for k in keys:
        if k.lower() in lower:
            return lower[k.lower()]
    return None


def _load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    df = df.dropna(how="all")
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    df["__source__"] = str(path)
    return df


def _row_to_dict(row: pd.Series) -> dict[str, str] | None:
    def pick(key: str) -> str:
        col = _resolve_col(row.to_frame().T, COL_ALIASES[key])
        val = row.get(col, "") if col else ""
        return "" if pd.isna(val) else str(val)

    title, abstract = pick("title"), pick("abstract")
    if not title and not abstract:
        return None
    return {
        "doc_type": "paper_row",
        "title": title or "(untitled)",
        "pmid": pick("pmid"),
        "authors": pick("authors"),
        "journal": pick("journal"),
        "year": pick("year"),
        "abstract": abstract,
        "impact_factor": pick("impact_factor"),
        "source": str(row.get("__source__", "table")),
        "text": _compose_paper_text(title, abstract, pick("pmid"), pick("journal"), pick("year")),
    }


def _compose_paper_text(title, abstract, pmid, journal, year) -> str:
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if journal or year:
        parts.append(f"Journal: {journal} {year}".strip())
    if pmid:
        parts.append(f"PMID: {pmid}")
    return "\n".join(parts) + "\n\nAbstract:\n" + (abstract or "(no abstract)")


# ---------------------------------------------------------------------------
# Curated doc loaders
# ---------------------------------------------------------------------------
def _docx_to_dict(path: Path) -> dict[str, str] | None:
    try:
        import docx

        d = docx.Document(str(path))
        text = "\n".join(p.text for p in d.paragraphs).strip()
    except Exception as exc:
        print(f"  ! failed to read {path.name}: {exc}")
        return None
    if not text:
        return None
    return {
        "doc_type": "curated_doc",
        "title": path.stem,
        "text": f"Teaching Document: {path.stem}\n\n{text}",
        "source": str(path),
    }


def _md_to_dict(path: Path) -> dict[str, str] | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        print(f"  ! failed to read {path.name}: {exc}")
        return None
    if not text:
        return None
    return {
        "doc_type": "curated_doc",
        "title": path.stem,
        "text": f"Teaching Document: {path.stem}\n\n{text}",
        "source": str(path),
    }


def _pdf_to_dict(path: Path) -> dict[str, str] | None:
    """Extract text from a PDF the user owns (PyPDF2, optional dependency)."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except ImportError:
        print(f"  ! PDF support needs: pip install PyPDF2 (skipping {path.name})")
        return None
    except Exception as exc:
        print(f"  ! failed to read {path.name}: {exc}")
        return None
    if not text:
        return None
    return {
        "doc_type": "curated_doc",
        "title": path.stem,
        "text": f"Document: {path.stem}\n\n{text}",
        "source": str(path),
    }


# ---------------------------------------------------------------------------
# Main ingest
# ---------------------------------------------------------------------------
def load_all_records(data_dir: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    tables = sorted([*data_dir.glob("*.xls*"), *data_dir.glob("*.csv")])
    for p in tables:
        try:
            df = _load_table(p)
            n0 = len(records)
            for _, row in df.iterrows():
                rec = _row_to_dict(row)
                if rec:
                    records.append(rec)
            print(f"Table {p.name}: {len(records) - n0} papers")
        except Exception as exc:
            print(f"  ! failed to read {p.name}: {exc}")

    for p in sorted(data_dir.glob("*.docx")):
        rec = _docx_to_dict(p)
        if rec:
            records.append(rec)
            print(f"Word doc: {p.name}")
    for p in sorted(data_dir.glob("*.md")):
        rec = _md_to_dict(p)
        if rec:
            records.append(rec)
            print(f"Markdown doc: {p.name}")
    for p in sorted(data_dir.glob("*.pdf")):
        rec = _pdf_to_dict(p)
        if rec:
            records.append(rec)
            print(f"PDF doc: {p.name}")

    return records


def build_indexes(records: list[dict[str, str]]) -> None:
    """Create FAISS (dense) + BM25 (sparse) indexes and persist them."""
    import jieba
    from rank_bm25 import BM25Okapi

    device = embedding_device()
    model_path = str(MODEL_DIR) if MODEL_DIR.exists() else EMBEDDING_MODEL_ID
    print(f"Embedding model: {model_path} (device: {device})")
    embeddings = HuggingFaceBgeEmbeddings(
        model_name=model_path,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )

    texts = [r["text"] for r in records]
    print(f"Building FAISS index for {len(texts)} documents ...")
    metadatas = [{k: v for k, v in r.items() if k != "text"} for r in records]
    db = FAISS.from_texts(texts, embeddings, metadatas=metadatas)

    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    db.save_local(str(VECTOR_DIR))

    print("Building BM25 lexical index ...")
    tokenized = [list(jieba.cut_for_search(t)) for t in texts]
    bm25 = BM25Okapi(tokenized)
    with open(VECTOR_DIR / BM25_FILE, "wb") as f:
        pickle.dump(bm25, f)
    with open(VECTOR_DIR / CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)

    print(f"Done. Indexes saved to {VECTOR_DIR}")


def main() -> None:
    seed_sample_data(DATA_DIR, Path(__file__).resolve().parents[1] / "assets")
    records = load_all_records(DATA_DIR)
    if not records:
        print(f"No documents found in {DATA_DIR}. Add xlsx/csv/docx/md and re-run.")
        return
    print(f"Total records: {len(records)}")
    build_indexes(records)


if __name__ == "__main__":
    main()
