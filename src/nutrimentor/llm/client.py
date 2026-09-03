"""Thin wrapper around any OpenAI-compatible chat endpoint.

Supports two modes:
  * invoke(prompt) -> full text (non-streaming)
  * stream(prompt) -> generator of text deltas (for SSE)
"""

from __future__ import annotations

from collections.abc import Generator

from nutrimentor.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)


class LLMClient:
    def __init__(self) -> None:
        if not LLM_API_KEY:
            raise RuntimeError(
                "LLM_API_KEY is not set. Copy .env.example to .env and add your key. "
                "Never commit keys to the repository."
            )
        from openai import OpenAI

        self._client = OpenAI(
            api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT
        )
        self.model = LLM_MODEL

    # ------------------------------------------------------------------
    def invoke(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            stream=False,
        )
        return resp.choices[0].message.content or ""

    def stream(self, prompt: str) -> Generator[str, None, None]:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            stream=True,
        )
        for event in resp:
            delta = event.choices[0].delta if event.choices else None
            if delta and delta.content:
                yield delta.content

    # Alias so langchain-style callers keep working
    def __call__(self, prompt: str) -> str:
        return self.invoke(prompt)


def make_client() -> LLMClient | None:
    try:
        return LLMClient()
    except Exception as exc:
        print(f"[llm] init failed: {exc}")
        return None
