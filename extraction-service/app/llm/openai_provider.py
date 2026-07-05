"""OpenAI provider — Chat Completions with JSON response format."""
import json
from typing import Iterator

from app.llm._json import extract_json_object


class OpenAiProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str | None = None,
                 max_retries: int = 5):
        from openai import OpenAI

        # base_url lets this drive any OpenAI-compatible endpoint (NVIDIA, etc.).
        # max_retries: SDK backs off on 429/5xx and respects Retry-After.
        self._client = OpenAI(api_key=api_key, max_retries=max_retries,
                              base_url=base_url or None)
        self.model = model
        # JSON-mode (response_format) is only reliably supported on the real
        # OpenAI API; on custom compatible endpoints we rely on the prompt +
        # extract_json_object, which is more portable.
        self._json_mode = not base_url
        self.last_usage: dict | None = None  # token usage of the last complete_json (EXT-02)

    def stream_chat(self, system_prompt: str, messages: list[dict], max_tokens: int = 2048) -> Iterator[str]:
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            stream=True,
            messages=[{"role": "system", "content": system_prompt}] + messages,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def complete_json(self, system_prompt: str, user_text: str, max_tokens: int = 8000) -> str:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        if self._json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        try:
            self.last_usage = {"input_tokens": resp.usage.prompt_tokens,
                               "output_tokens": resp.usage.completion_tokens}
        except Exception:
            self.last_usage = None
        return json.dumps(extract_json_object(resp.choices[0].message.content or ""))
