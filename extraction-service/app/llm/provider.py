"""LLM provider protocol. A provider turns (system_prompt, user_text) into a JSON
string. Add a provider by implementing this and registering it in factory.py."""
from __future__ import annotations

from typing import Iterator, Protocol


class LlmProvider(Protocol):
    name: str

    def complete_json(self, system_prompt: str, user_text: str, max_tokens: int = 8000) -> str:
        """Return the model's reply as a JSON string (object extracted from the
        reply text). Raises json.JSONDecodeError if no JSON object is found."""
        ...

    def stream_chat(self, system_prompt: str, messages: list[dict], max_tokens: int = 2048) -> Iterator[str]:
        """Yield plain-text token chunks for a (multi-turn) chat. `messages` is a
        list of {"role": "user"|"assistant", "content": str} in order."""
        ...
