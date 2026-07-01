"""OpenAI provider — Chat Completions with JSON response format."""
import json
from typing import Iterator

from app.llm._json import extract_json_object


class OpenAiProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, max_retries=3)
        self.model = model

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
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        )
        return json.dumps(extract_json_object(resp.choices[0].message.content or ""))
