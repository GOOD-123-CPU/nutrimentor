"""Interactive terminal chat for any persona."""

from __future__ import annotations

import sys


def main(persona: str = "teacher") -> int:
    from nutrimentor.engine import get_engine

    engine = get_engine(persona)
    if engine is None:
        print("Engine init failed. Check .env (LLM_API_KEY) and run ingest first.")
        return 1
    if not engine.retriever_ready:
        print("Vector index missing — run: nutrimentor ingest")

    print(f"\nNutriMentor CLI [{persona}] — type a question, 'exit' to quit.\n")
    session_id = None
    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query.lower() == "exit":
            break
        if not query:
            continue
        result = engine.ask(query, session_id=session_id)
        session_id = result["session_id"]
        print(f"\n{result['result']}\n")
        if result["sources"]:
            print("--- Sources ---")
            for i, s in enumerate(result["sources"], 1):
                pmid = f" | PMID:{s['pmid']}" if s["pmid"] else ""
                print(f"  {i}. {s['title']}{pmid} | score {s['score']:.3f}")
        print("\n" + "-" * 46 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
