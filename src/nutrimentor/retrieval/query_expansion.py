"""Query expansion for better recall on domain-specific questions.

Lightweight, rule-based (no extra LLM call): normalises common nutrition
term variants so the BM25 leg catches them, e.g. "维D" → "维生素D 维生素D3",
"omega3" → "omega-3 欧米伽3". Cheap, transparent, and easy to extend via
the alias table.
"""

from __future__ import annotations

import re

# canonical term -> list of synonym variants to append
ALIASES: dict[str, list[str]] = {
    "维生素d": ["维生素D", "维生素D3", "维D", "25-羟维生素D"],
    "维d": ["维生素D", "维生素D3"],
    "omega3": ["omega-3", "欧米伽3", "n-3多不饱和脂肪酸"],
    "欧米伽3": ["omega-3", "n-3多不饱和脂肪酸"],
    "dha": ["DHA", "二十二碳六烯酸", "omega-3"],
    "epa": ["EPA", "二十碳五烯酸"],
    "钙": ["钙", "Ca", "钙摄入"],
    "铁": ["铁", "Fe", "铁缺乏", "缺铁性"],
    "锌": ["锌", "Zn"],
    "膳食纤维": ["膳食纤维", "纤维", "益生元"],
    "益生菌": ["益生菌", "肠道菌群", "乳酸杆菌", "双歧杆菌"],
    "肠道菌群": ["肠道菌群", "微生物组", "microbiota"],
    "血糖": ["血糖", "葡萄糖代谢", "糖耐量"],
    "肥胖": ["肥胖", "超重", "bmi"],
    "自闭症": ["自闭症", "孤独症", "asd"],
    "多动症": ["多动症", "adhd", "注意缺陷"],
}

_MAX_EXPANSION = 4  # never balloon the query


def expand_query(query: str) -> str:
    """Return the query with appended synonym variants (deduplicated)."""
    q = query.strip()
    if not q:
        return q
    lower = q.lower()
    additions: list[str] = []
    for key, variants in ALIASES.items():
        if key in lower:
            for v in variants:
                if v.lower() not in lower and v not in additions:
                    additions.append(v)
            if len(additions) >= _MAX_EXPANSION:
                break
    if not additions:
        return q
    return q + " " + " ".join(additions[:_MAX_EXPANSION])


def tokenize_for_bm25(query: str, jieba_mod=None) -> list[str]:
    """Tokenise with jieba if available; fallback to regex word split."""
    if jieba_mod is not None:
        return list(jieba_mod.cut_for_search(expand_query(query)))
    return re.findall(r"[\w\u4e00-\u9fff]+", expand_query(query))
