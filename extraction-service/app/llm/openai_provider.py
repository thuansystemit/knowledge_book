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
        # GPT-5-era / reasoning models reject `max_tokens` and require
        # `max_completion_tokens`.  Probe-and-cache the right name (like json_mode):
        # None = not yet probed, else the resolved kwarg name.
        self._token_param: str | None = None
        self.last_usage: dict | None = None  # token usage of the last complete_json (EXT-02)

    def _token_kwargs(self, n: int) -> dict:
        """The output-length kwarg under whichever name this model accepts."""
        return {self._token_param or "max_tokens": n}

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
        base = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
        }
        try:
            resp = self._client.chat.completions.create(**base, **self._token_kwargs(max_tokens))
        except Exception as e:
            if self._token_param is None and _is_max_tokens_param_rejection(e):
                self._token_param = "max_completion_tokens"
                audit("TOKEN_PARAM_PROBE", result="max_completion_tokens", model=self.model)
                resp = self._client.chat.completions.create(**base, **self._token_kwargs(max_tokens))
            else:
                raise
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def complete_json(self, system_prompt: str, user_text: str, max_tokens: int = 8000,
                      temperature: float | None = None) -> str:
        kwargs: dict = {
            "model": self.model,
            **self._token_kwargs(max_tokens),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        use_json_mode = self._should_use_json_mode()
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            # A single 400 may flag either capability; adapt (cache) and retry.
            adapted = False
            # GPT-5-era models reject `max_tokens` -> switch to max_completion_tokens.
            if self._token_param is None and _is_max_tokens_param_rejection(e):
                self._token_param = "max_completion_tokens"
                audit("TOKEN_PARAM_PROBE", result="max_completion_tokens",
                      model=self.model, error=str(e)[:200])
                kwargs.pop("max_tokens", None)
                kwargs.update(self._token_kwargs(max_tokens))
                adapted = True
            # EFT-05: if the endpoint rejects response_format with a 400/422,
            # fall back to prompt-only for this process.
            if (use_json_mode and self._json_mode_setting == "auto"
                    and _is_json_mode_rejection(e) and not _is_max_tokens_param_rejection(e)):
                self._json_mode_resolved = False
                use_json_mode = False
                audit("JSON_MODE_PROBE", result="unsupported", model=self.model,
                      error=str(e)[:200])
                kwargs.pop("response_format", None)
                adapted = True
            if not adapted:
                raise
            resp = self._client.chat.completions.create(**kwargs)

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


def _is_max_tokens_param_rejection(exc: Exception) -> bool:
    """Check if a 400 says `max_tokens` is unsupported (GPT-5-era / reasoning
    models require `max_completion_tokens` instead).  Matched on the error
    message so it works across SDK exception shapes."""
    msg = str(getattr(exc, "message", "") or exc).lower()
    return "max_tokens" in msg and (
        "max_completion_tokens" in msg
        or "unsupported parameter" in msg
        or "not supported" in msg
    )


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
