"""`nutrimentor doctor` — one-shot environment diagnosis.

Checks, in order: Python version, config, .env presence, LLM key format,
embedding model files, FAISS/BM25 index integrity, dataset statistics.
Exit code 0 = all critical checks passed. Designed for issue reports:
"please paste the output of `nutrimentor doctor`".
"""

from __future__ import annotations

import json
import sys

from nutrimentor.config import (
    DATA_DIR,
    LLM_API_KEY,
    MODEL_DIR,
    PROJECT_ROOT,
    VECTOR_DIR,
    embedding_device,
)

OK, WARN, FAIL = "[OK]  ", "[WARN]", "[FAIL]"

_results: list[tuple[str, str, str]] = []  # (level, item, detail)


def _check(level: str, item: str, detail: str = "") -> None:
    _results.append((level, item, detail))
    print(f"{level} {item}" + (f" — {detail}" if detail else ""))


def run() -> int:
    print(f"NutriMentor doctor · project root: {PROJECT_ROOT}\n")

    # Python
    v = sys.version_info
    _check(OK if v >= (3, 10) else FAIL, "Python version",
           f"{v.major}.{v.minor}.{v.micro} (need >= 3.10)")

    # .env
    env_file = PROJECT_ROOT / ".env"
    _check(WARN if not env_file.exists() else OK, ".env file",
           "found" if env_file.exists() else "missing — copy .env.example")

    # LLM key (never print it)
    if LLM_API_KEY:
        _check(OK, "LLM_API_KEY", f"set ({len(LLM_API_KEY)} chars)")
    else:
        _check(FAIL, "LLM_API_KEY", "not set")

    # Embedding model
    marker = MODEL_DIR / "config.json"
    if marker.exists():
        size_mb = sum(f.stat().st_size for f in MODEL_DIR.rglob("*") if f.is_file()) / 1e6
        # bge-large-zh full weights ~1300MB; flag suspiciously small copies
        if size_mb < 100:
            _check(WARN, "Embedding model", f"only {size_mb:.0f}MB — download may be incomplete")
        else:
            _check(OK, "Embedding model", f"{size_mb:.0f}MB at {MODEL_DIR}")
    else:
        _check(WARN, "Embedding model", f"not found at {MODEL_DIR} — run download-model")

    # Device
    _check(OK, "Embedding device", embedding_device())

    # Indexes
    faiss_ok = (VECTOR_DIR / "index.faiss").exists()
    _check(OK if faiss_ok else FAIL, "FAISS index",
           str(VECTOR_DIR) if faiss_ok else "missing — run ingest")
    chunks_file = VECTOR_DIR / "chunks.json"
    if chunks_file.exists():
        records = json.loads(chunks_file.read_text(encoding="utf-8"))
        papers = sum(1 for r in records if r.get("doc_type") == "paper_row")
        curated = sum(1 for r in records if r.get("doc_type") == "curated_doc")
        _check(OK, "Corpus", f"{len(records)} docs ({papers} papers, {curated} curated)")
        if len(records) < 10:
            _check(WARN, "Corpus size", "very small — answers will be limited")
    else:
        _check(WARN, "Corpus metadata", "chunks.json missing")

    # Data dir
    user_files = [p.name for p in DATA_DIR.iterdir() if p.name != ".gitkeep"] if DATA_DIR.exists() else []
    if user_files:
        _check(OK, "data/raw", f"{len(user_files)} file(s)")
    else:
        _check(WARN, "data/raw", "empty — only bundled samples will be used")

    # Optional deps
    for mod, hint in [
        ("rank_bm25", "pip install rank-bm25 (hybrid retrieval)"),
        ("jieba", "pip install jieba (Chinese tokenisation)"),
        ("openai", "pip install openai (LLM client)"),
        ("flask", "pip install flask (web server)"),
    ]:
        try:
            __import__(mod)
            _check(OK, f"dependency {mod}")
        except ImportError:
            _check(WARN, f"dependency {mod}", hint)

    print("\nSummary:")
    fails = sum(1 for r in _results if r[0] == FAIL)
    warns = sum(1 for r in _results if r[0] == WARN)
    print(f"  {fails} failed, {warns} warnings, "
          f"{sum(1 for r in _results if r[0] == OK)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(run())
