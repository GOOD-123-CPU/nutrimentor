# Architecture

## High-level data flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        KNOWLEDGE INGESTION                       │
│                                                                  │
│  data/raw/                                                       │
│  ├── *.xlsx / *.csv   paper tables (PMID, Title, Abstract …)     │
│  ├── *.docx / *.md    curated teaching documents                 │
│  └── *.pdf            owned documents (optional PyPDF2)          │
│         │                                                        │
│         ▼  nutrimentor ingest                                    │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐    │
│  │ FAISS index  │   │ BM25 index   │   │ chunks.json      │    │
│  │ (BGE dense)  │   │ (jieba lex)  │   │ (source metadata)│    │
│  └──────────────┘   └──────────────┘   └──────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     QUERY-TIME PIPELINE                          │
│                                                                  │
│  question ──► query expansion (synonym aliases)                  │
│        │                                                         │
│        ├──► dense search  (FAISS, top-20)                        │
│        ├──► sparse search (BM25, top-20)                         │
│        │                                                         │
│        ▼                                                         │
│  RRF fusion (k=60) ──► curated-doc bonus                         │
│        │                                                         │
│        ▼                                                         │
│  [optional] cross-encoder rerank (bge-reranker-base)             │
│        │                                                         │
│        ▼                                                         │
│  relevance threshold ──► refuse if below (anti-hallucination)    │
│        │                                                         │
│        ▼                                                         │
│  MentorEngine ──► persona prompt + session history ──► LLM       │
│        │                                                         │
│        ├── REST       /{persona}/api/ask                         │
│        └── SSE stream /{persona}/api/ask/stream                  │
└─────────────────────────────────────────────────────────────────┘
```

## Key design decisions

### Why hybrid retrieval?
Dense vectors capture semantics ("sweets" ≈ "candy") but miss exact terms
("维生素D3" vs "维D"); BM25 nails keywords but misses paraphrase. RRF merges
both rankings scale-free — no score normalisation needed.

### Why a relevance threshold?
RAG systems fail hardest when the corpus simply lacks the answer: the LLM
confidently hallucinates from weak context. We compute a fused score and
refuse gracefully below `NM_RELEVANCE_THRESHOLD` (0.25 default). Honest
"not in corpus" beats plausible nonsense for an education product.

### Why three personas, one engine?
The retrieval pipeline is identical; only the prompt and canned responses
differ. This guarantees consistency (same facts available to everyone) and
halves the maintenance surface versus the pre-fork two-codebase design.

### Why SQLite for sessions?
Zero-dependency persistence (stdlib), survives restarts, enables audit.
The interface (ensure_session / append_turn / history_text) is 3 methods —
swapping in Redis/Postgres later is a drop-in change.

## Module map

| Module | Responsibility |
|--------|----------------|
| `config.py` | 12-factor config, env-var overrides, device auto-detect |
| `engine.py` | MentorEngine facade, personas, relevance gate |
| `sessions.py` | SQLite session store (thread-safe, WAL) |
| `prompts.py` | Persona templates + canned responses |
| `retrieval/hybrid.py` | Dense+sparse retrieval, RRF fusion |
| `retrieval/query_expansion.py` | Domain synonym aliases |
| `retrieval/reranker.py` | Optional CrossEncoder stage |
| `retrieval/ingest.py` | Corpus loading, index building |
| `evaluation.py` | Recall@K / MRR offline evaluation |
| `doctor.py` | Environment diagnosis (`nutrimentor doctor`) |
| `llm/client.py` | OpenAI-compatible client (invoke/stream) |
| `servers/flask_app.py` | REST + SSE routes, 3 personas |
