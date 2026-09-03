"""Flask server exposing REST + SSE endpoints for all three personas.

Routes:
    GET  /                          landing page
    GET  /{persona}/                chat UI (student | teacher | researcher)
    GET  /{persona}/api/health      readiness probe
    POST /{persona}/api/ask         JSON answer  {question, session_id?}
    POST /{persona}/api/ask/stream  SSE stream   {question, session_id?}
"""

from __future__ import annotations

import argparse

from flask import Blueprint, Flask, Response, jsonify, render_template, request, stream_with_context

from nutrimentor.config import DEBUG, HOST, PORT
from nutrimentor.engine import VALID_PERSONAS, get_engine

app = Flask(
    __name__,
    template_folder=str(__import__("pathlib").Path(__file__).parent / "templates"),
)

blueprints: dict[str, Blueprint] = {}
for persona in VALID_PERSONAS:
    bp = Blueprint(persona, __name__, url_prefix=f"/{persona}")
    engine = get_engine(persona)

    @bp.get("/")
    def index(persona=persona):
        return render_template("chat.html", persona=persona)

    @bp.get("/api/health")
    def health(persona=persona, engine=engine):
        ok = engine is not None and engine.retriever_ready
        return jsonify({"status": "ok" if ok else "error", "persona": persona})

    @bp.post("/api/ask")
    def ask(persona=persona, engine=engine):
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        if not question:
            return jsonify({"ok": False, "error": "empty question"}), 400
        if engine is None:
            return jsonify({"ok": False, "error": "engine not initialised"}), 503
        result = engine.ask(question, session_id=payload.get("session_id"))
        return jsonify({"ok": True, **result})

    @bp.post("/api/ask/stream")
    def ask_stream(persona=persona, engine=engine):
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        if not question:
            return jsonify({"ok": False, "error": "empty question"}), 400
        if engine is None:
            return jsonify({"ok": False, "error": "engine not initialised"}), 503

        def generate():
            yield from engine.ask_stream(question, session_id=payload.get("session_id"))

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    blueprints[persona] = bp
    app.register_blueprint(bp)


@app.get("/")
def home():
    return render_template("landing.html")


def create_app() -> Flask:
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="NutriMentor web server")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--reload", action="store_true", help="dev auto-reload")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=DEBUG or args.reload,
            use_reloader=args.reload)


if __name__ == "__main__":
    main()
