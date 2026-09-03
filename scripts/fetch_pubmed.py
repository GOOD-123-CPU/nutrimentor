#!/usr/bin/env python3
"""Query PubMed E-utilities and export paper metadata to CSV.

The output CSV matches the schema ingest.py expects (PMID, Title, Authors,
Journal, Year, Abstract, Impact Factor) so you can drop it straight into
data/raw and rebuild the vector store.

Usage:
    python scripts/fetch_pubmed.py "child nutrition gut microbiota" \
        --max 50 --out data/raw/pubmed_child_nutrition.csv

Notes:
* Only metadata + abstracts are stored (public-domain via NCBI E-utilities).
* No full texts are downloaded; respect publishers' rights.
* A PUBMED_API_KEY in .env raises your rate limit from 3 to 10 req/s.
"""

from __future__ import annotations

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests


from nutrimentor.config import PUBMED_API_KEY, PUBMED_EMAIL, PUBMED_TOOL

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _params(extra: dict) -> dict:
    p = {"tool": PUBMED_TOOL, "email": PUBMED_EMAIL}
    if PUBMED_API_KEY:
        p["api_key"] = PUBMED_API_KEY
    p.update(extra)
    return p


def search_pmids(query: str, limit: int) -> list[str]:
    resp = requests.get(
        ESEARCH,
        params=_params({"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"}),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["esearchresult"].get("idlist", [])


def _text(node, path: str) -> str:
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else ""


def fetch_records(pmids: list[str]) -> list[dict]:
    rows = []
    for chunk_start in range(0, len(pmids), 50):
        chunk = pmids[chunk_start : chunk_start + 50]
        resp = requests.get(
            EFETCH,
            params=_params({"db": "pubmed", "id": ",".join(chunk), "retmode": "xml"}),
            timeout=60,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        for art in root.iter("PubmedArticle"):
            medline = art.find(".//MedlineCitation")
            article = medline.find("Article") if medline is not None else None
            if article is None:
                continue

            pmid = _text(medline, "PMID")
            title = _text(article, "ArticleTitle")
            abstract = " ".join(
                t.text.strip() for t in article.findall(".//Abstract/AbstractText") if t.text
            )
            journal = _text(article, "Journal/Title")
            year = _text(article, "Journal/JournalIssue/PubDate/Year") or _text(
                article, "Journal/JournalIssue/PubDate/MedlineDate"
            )
            authors = "; ".join(
                f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip()
                for a in article.findall(".//Author")
                if a.find("LastName") is not None
            )
            rows.append(
                {
                    "PMID": pmid,
                    "Title": title,
                    "Authors": authors,
                    "Journal": journal,
                    "Year": year,
                    "Abstract": abstract,
                    "Impact Factor": "",
                }
            )
        time.sleep(0.4)  # be polite to NCBI
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch PubMed metadata to CSV")
    parser.add_argument("query", help="PubMed search query")
    parser.add_argument("--max", type=int, default=50, help="max records (default 50)")
    parser.add_argument(
        "--out", default="data/raw/pubmed_results.csv", help="output CSV path"
    )
    args = parser.parse_args()

    print(f"Searching PubMed for: {args.query!r} (max {args.max})")
    pmids = search_pmids(args.query, args.max)
    if not pmids:
        print("No results.")
        return 1
    print(f"Found {len(pmids)} PMIDs. Fetching metadata ...")

    rows = fetch_records(pmids)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(rows)} records to {out_path}")
    print("Next: python ingest.py   (rebuild the vector store)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
