# Changelog

All notable changes to NutriMentor are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/).

## [1.0.0] - 2026-09-03

### Added
- Three persona-aware tutoring engine: student (child-friendly), teacher
  (academic), researcher (evidence-graded literature review)
- Hybrid retrieval: FAISS dense (BGE) + BM25 sparse (jieba) fused with
  Reciprocal Rank Fusion; curated teaching docs receive rank bonus
- Query expansion with nutrition-domain synonym aliases
- Optional cross-encoder reranking (`NM_RERANKER=1`, bge-reranker-base)
- Relevance thresholding — honest refusals instead of hallucination
- SQLite session persistence (WAL, thread-safe, TTL cleanup)
- Streaming answers via Server-Sent Events; sources event precedes deltas
- Offline evaluation framework (`nutrimentor evaluate`): Recall@K, MRR
- Environment diagnostics (`nutrimentor doctor`)
- CLI: `nutrimentor serve|ingest|download-model|chat|test-api|doctor|evaluate`
- Corpus ingestion: xlsx/csv paper tables, docx/md curated docs, PDF (optional)
- PubMed E-utilities fetch script (metadata only, public domain)
- Dockerfile (non-root, healthcheck) + docker-compose
- GitHub Actions CI: ruff + pytest (3.10/3.11/3.12) + docker build
- 22 offline unit tests; secret-scan test included
- MIT LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY policy

### Security
- All credentials via `.env`; repository ships zero secrets
- `detect-private-key` pre-commit hook; CI secret scan
