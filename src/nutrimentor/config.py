"""Central configuration for NutriMentor.

Every value can be overridden by environment variables (12-factor style).
Secrets NEVER live here — they are read from the local, git-ignored .env.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Locate project root: works both when running from source (src layout)
# and when running from an installed console script.
_HERE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (p for p in [_HERE.parent, *_HERE.parents] if (p / "pyproject.toml").exists()),
    _HERE.parents[2],
)

load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.getenv("NM_DATA_DIR", PROJECT_ROOT / "data" / "raw"))
VECTOR_DIR = Path(os.getenv("NM_VECTOR_DIR", PROJECT_ROOT / "vector_store"))
MODEL_DIR = Path(os.getenv("NM_MODEL_DIR", PROJECT_ROOT / "models" / "bge-large-zh"))

# ---------------------------------------------------------------------------
# LLM (any OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_ID = os.getenv("NM_EMBEDDING_MODEL_ID", "BAAI/bge-large-zh-v1.5")


def embedding_device() -> str:
    """Resolve device: EMBEDDING_DEVICE env var, or auto-detect."""
    pref = os.getenv("EMBEDDING_DEVICE", "auto").lower()
    if pref != "auto":
        return pref
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
RETRIEVAL_K = int(os.getenv("NM_RETRIEVAL_K", "8"))          # per-engine candidates
HYBRID_CANDIDATES = int(os.getenv("NM_HYBRID_K", "20"))       # pool before fusion
FINAL_TOP_K = int(os.getenv("NM_TOP_K", "5"))                 # docs into the prompt
CURATED_PRIORITY = int(os.getenv("NM_CURATED_PRIORITY", "2")) # bonus slots for curated
RELEVANCE_THRESHOLD = float(os.getenv("NM_RELEVANCE_THRESHOLD", "0.25"))
# Docs whose best fused score falls below this are treated as irrelevant.

# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------
MEMORY_MAX_TURNS = int(os.getenv("NM_MEMORY_TURNS", "6"))     # kept turns per session

# ---------------------------------------------------------------------------
# Optional PubMed E-utilities
# ---------------------------------------------------------------------------
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
PUBMED_TOOL = os.getenv("PUBMED_TOOL", "nutrimentor")
PUBMED_EMAIL = os.getenv("PUBMED_EMAIL", "")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
