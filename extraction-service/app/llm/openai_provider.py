"""OpenAI provider — Chat Completions with capability-aware JSON response format.

EFT-05: `json_mode` controls whether `response_format={"type":"json_object"}`
is sent.  "auto" (default) sends it optimistically and, on a 400/422 from the
endpoint, falls back to prompt-only for the rest of the process (caches the
probe result).  "force" always sends it.  "off" never sends it (matches the
pre-EFT-05 behavior for custom base_url endpoints)."""
import json
from typing import Iterator

from app.llm._json import extract_json_object
from app.observability import audit


class OpenAiProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str | None = None,
                 max_retries: int = 5, json_mode: str = "auto"):
        from openai import OpenAI

        # base_url lets this drive any OpenAI-compatible endpoint (NVIDIA, etc.).
        # max_retries: SDK backs off on 429/5xx and respects Retry-After.
        self._client = OpenAI(api_key=api_key, max_retries=max_retries,
                              base_url=base_url or None)
        self.model = model
        # EFT-05: capability-aware JSON mode.
        self._json_mode_setting = json_mode.strip().lower()  # "auto" | "force" | "off"
        # None = not yet probed (only relevant for "auto").
        self._json_mode_resolved: bool | None = None
        self.last_usage: dict | None = None  # token usage of the last complete_json (EXT-02)

    def _should_use_json_mode(self) -> bool:
        """Decide whether to send response_format on this call."""
        if self._json_mode_setting == "off":
            return False
        if self._json_mode_setting == "force":
            return True
        # "auto": use cached probe result, or default to True (probe on error).
        if self._json_mode_resolved is not None:
            return self._json_mode_resolved
        return True  # optimistic; if 400/422, _complete_json_inner catches + caches

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
        use_json_mode = self._should_use_json_mode()
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            # EFT-05 auto-detection: if the endpoint rejects response_format
            # with a 400 or 422, fall back to prompt-only for this process.
            if (use_json_mode and self._json_mode_setting == "auto"
                    and _is_json_mode_rejection(e)):
                self._json_mode_resolved = False
                audit("JSON_MODE_PROBE", result="unsupported", model=self.model,
                      error=str(e)[:200])
                # Retry the same call without response_format.
                kwargs.pop("response_format", None)
                resp = self._client.chat.completions.create(**kwargs)
            else:
                raise

        # If we got here with json_mode and auto, the endpoint supports it.
        if use_json_mode and self._json_mode_setting == "auto" and self._json_mode_resolved is None:
            self._json_mode_resolved = True
            audit("JSON_MODE_PROBE", result="supported", model=self.model)

        try:
            self.last_usage = {"input_tokens": resp.usage.prompt_tokens,
                               "output_tokens": resp.usage.completion_tokens}
        except Exception:
            self.last_usage = None
        return json.dumps(extract_json_object(resp.choices[0].message.content or ""))


def _is_json_mode_rejection(exc: Exception) -> bool:
    """Check if an OpenAI SDK exception is a 400/422 that indicates the endpoint
    does not support response_format.  Works with openai.BadRequestError (400)
    and openai.UnprocessableEntityError (422)."""
    status = getattr(exc, "status_code", None)
    if status in (400, 422):
        return True
    # Some SDK versions use .code or .http_status instead.
    code = getattr(exc, "code", None) or getattr(exc, "http_status", None)
    if code in (400, 422):
        return True
    return False
