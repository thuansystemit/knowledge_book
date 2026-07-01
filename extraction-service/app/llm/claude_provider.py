"""Anthropic Claude provider — official SDK.

Per the Claude API guidance (claude-api skill): default model claude-opus-4-8;
adaptive thinking; NO temperature / top_p / budget_tokens on Opus 4.8 (they 400).
The system prompt instructs the model to return only a JSON object; we extract
that object from the response text, which works on the installed SDK without
depending on the newer structured-output API."""
import json
from typing import Iterator

from app.llm._json import extract_json_object


class ClaudeProvider:
    name = "claude"

    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic

        # max_retries -> SDK exponential backoff on 429/5xx/overloaded/timeout.
        self._client = Anthropic(api_key=api_key, max_retries=3)
        self.model = model

    def stream_chat(self, system_prompt: str, messages: list[dict], max_tokens: int = 2048) -> Iterator[str]:
        # Plain-text chat: no JSON schema, no thinking needed.
        with self._client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def complete_json(self, system_prompt: str, user_text: str, max_tokens: int = 8000) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},  # Opus 4.8: adaptive only
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        )
        return json.dumps(extract_json_object(text))
