"""Smoke-test the configured LLM endpoint. Never prints the key."""

from __future__ import annotations

import sys

from nutrimentor.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def main() -> int:
    if not LLM_API_KEY:
        print("LLM_API_KEY not set. Copy .env.example to .env and fill it in.")
        return 1

    from openai import OpenAI

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say OK in one word."},
            ],
            stream=False,
        )
        print("OK:", resp.choices[0].message.content)
        return 0
    except Exception as exc:
        print("FAILED:", repr(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
