"""Ollama provider — local models via the /api/chat endpoint (no API key)."""
import json
import urllib.request
from typing import Iterator

from app.llm._json import extract_json_object


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.last_usage: dict | None = None  # local model — no metered cost (EXT-02)

    def stream_chat(self, system_prompt: str, messages: list[dict], max_tokens: int = 2048) -> Iterator[str]:
        body = json.dumps({
            "model": self.model,
            "stream": True,  # native token streaming; NOT format=json (plain text)
            "options": {"num_predict": max_tokens},
            "messages": [{"role": "system", "content": system_prompt}] + messages,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            for line in r:
                line = line.strip()
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    return

    def complete_json(self, system_prompt: str, user_text: str, max_tokens: int = 8000,
                      temperature: float | None = None) -> str:
        payload_body: dict = {
            "model": self.model,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        if temperature is not None:
            payload_body["options"] = {"temperature": temperature}
        body = json.dumps(payload_body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            payload = json.loads(r.read().decode("utf-8"))
        return json.dumps(extract_json_object(payload.get("message", {}).get("content", "")))
