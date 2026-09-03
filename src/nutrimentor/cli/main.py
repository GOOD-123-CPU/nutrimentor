"""`nutrimentor` console entrypoint with subcommands.

Usage:
    nutrimentor serve [--persona student|teacher|researcher]
    nutrimentor ingest
    nutrimentor download-model
    nutrimentor chat [--persona ...]
    nutrimentor test-api
"""

from __future__ import annotations

import argparse
import sys


def _serve(args: argparse.Namespace) -> int:
    from nutrimentor.servers.flask_app import main as flask_main

    sys.argv = ["nutrimentor", "--host", args.host, "--port", str(args.port)]
    if args.reload:
        sys.argv.append("--reload")
    flask_main()
    return 0


def _ingest(_args: argparse.Namespace) -> int:
    from nutrimentor.retrieval.ingest import main as ingest_main

    ingest_main()
    return 0


def _download_model(_args: argparse.Namespace) -> int:
    from nutrimentor.cli.download_model import main as dm

    return dm()


def _chat(args: argparse.Namespace) -> int:
    from nutrimentor.cli.chat import main as chat_main

    return chat_main(persona=args.persona)


def _test_api(_args: argparse.Namespace) -> int:
    from nutrimentor.cli.test_api import main as ta

    return ta()


def _doctor(_args: argparse.Namespace) -> int:
    from nutrimentor.doctor import run

    return run()


def _evaluate(args: argparse.Namespace) -> int:
    from nutrimentor.evaluation import main as ev

    argv = ([args.eval_set] if args.eval_set else []) + (
        ["--k", str(args.k)] if args.k != 5 else []
    )
    return ev(argv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nutrimentor", description="AI-powered nutrition education platform"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="start the web server")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=_serve)

    p_ing = sub.add_parser("ingest", help="build FAISS + BM25 indexes from data/raw")
    p_ing.set_defaults(func=_ingest)

    p_dm = sub.add_parser("download-model", help="download the BGE embedding model")
    p_dm.set_defaults(func=_download_model)

    p_chat = sub.add_parser("chat", help="interactive terminal chat")
    p_chat.add_argument("--persona", default="teacher",
                        choices=["student", "teacher", "researcher"])
    p_chat.set_defaults(func=_chat)

    p_ta = sub.add_parser("test-api", help="smoke-test the LLM endpoint")
    p_ta.set_defaults(func=_test_api)

    p_doc = sub.add_parser("doctor", help="diagnose environment & index health")
    p_doc.set_defaults(func=_doctor)

    p_ev = sub.add_parser("evaluate", help="evaluate retrieval quality (Recall@K / MRR)")
    p_ev.add_argument("eval_set", nargs="?", default=None,
                      help="JSON file with labelled questions")
    p_ev.add_argument("--k", type=int, default=5)
    p_ev.set_defaults(func=_evaluate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
