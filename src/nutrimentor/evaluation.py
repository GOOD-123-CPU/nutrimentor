"""Retrieval quality evaluation framework.

Run a labelled question set through the retriever (no LLM needed) and
report Recall@K / MRR per persona-agnostic corpus. Ships with a small
built-in eval set for the bundled sample corpus; users can drop a JSON
file with their own ground truth:

    [
      {"question": "...", "relevant": ["PMID:12345", "doc-title-substring"]}
    ]

Usage:
    python -m nutrimentor.evaluation            # built-in sample set
    python -m nutrimentor.evaluation my_set.json --k 10
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from nutrimentor.retrieval.hybrid import HybridRetriever

# Built-in eval set matching the bundled sample corpus
BUILTIN_EVAL = [
    {
        "question": "膳食纤维对儿童肠道菌群有什么影响？",
        "relevant": ["膳食纤维", "fiber", "microbiota"],
    },
    {
        "question": "含糖饮料对青少年注意力有什么影响？",
        "relevant": ["sugar", "attention", "adolescen"],
    },
    {
        "question": "早餐质量和儿童情绪有什么关系？",
        "relevant": ["breakfast", "mood"],
    },
    {
        "question": "彩虹餐盘是什么教学方法？",
        "relevant": ["彩虹餐盘"],
    },
    {
        "question": "零食应该怎么分级？",
        "relevant": ["零食", "绿灯"],
    },
]


def _is_relevant(chunk, relevant_terms: list[str]) -> bool:
    haystack = f"{chunk.title} {chunk.text}".lower()
    return any(t.lower() in haystack for t in relevant_terms)


def evaluate(eval_set: list[dict], k: int = 5, verbose: bool = True) -> dict:
    retriever = HybridRetriever()
    if not retriever.load():
        print("Retriever not ready — run ingest first.")
        return {}

    recalls, mrrs = [], []
    for item in eval_set:
        chunks, _ = retriever.retrieve(item["question"])
        top = chunks[:k]
        hit_rank = next(
            (i + 1 for i, c in enumerate(top) if _is_relevant(c, item["relevant"])),
            None,
        )
        recall = 1.0 if hit_rank else 0.0
        mrr = 1.0 / hit_rank if hit_rank else 0.0
        recalls.append(recall)
        mrrs.append(mrr)
        if verbose:
            mark = f"hit@{hit_rank}" if hit_rank else "MISS"
            print(f"  [{'OK' if hit_rank else '!!'}] {item['question'][:36]:<38} {mark}")

    n = len(recalls) or 1
    return {
        "queries": len(recalls),
        f"recall@{k}": sum(recalls) / n,
        "mrr": sum(mrrs) / n,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate retrieval quality")
    parser.add_argument("eval_set", nargs="?", default=None,
                        help="JSON file with labelled questions (optional)")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args(argv)

    if args.eval_set:
        data = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))
    else:
        data = BUILTIN_EVAL

    print(f"Evaluating {len(data)} queries (k={args.k}) ...\n")
    metrics = evaluate(data, k=args.k)
    if metrics:
        print("\n=== Metrics ===")
        for k_, v in metrics.items():
            print(f"  {k_}: {v:.3f}" if isinstance(v, float) else f"  {k_}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
