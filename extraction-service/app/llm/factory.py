"""Select an LlmProvider by name (live .env-driven). Add a provider here once."""
from __future__ import annotations

from app.config import get_settings
from app.llm.provider import LlmProvider


def get_provider(name: str | None = None, model: str | None = None) -> LlmProvider:
    cfg = get_settings()
    name = (name or cfg.provider).lower()

    if name == "claude":
        from app.llm.claude_provider import ClaudeProvider

        if not cfg.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        return ClaudeProvider(cfg.anthropic_api_key, model or cfg.anthropic_model,
                              max_retries=cfg.llm_max_retries)

    if name == "openai":
        from app.llm.openai_provider import OpenAiProvider

        if not cfg.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return OpenAiProvider(cfg.openai_api_key, model or cfg.openai_model,
                              base_url=cfg.openai_base_url,
                              max_retries=cfg.llm_max_retries,
                              json_mode=cfg.openai_json_mode)

    if name == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(cfg.ollama_base_url, model or cfg.ollama_model)

    raise ValueError(f"unknown LLM provider: {name}")


def model_available(provider: LlmProvider) -> bool:
    """Cheap reachability check: is this provider's model actually served right now?

    Regeneration/retry must not blindly trust a model recorded on an old job (a
    model can be removed from the endpoint — e.g. a 404 on `gpt-5.6-luna`). One
    tiny completion tells us whether the model exists before we burn the full
    retry budget on it. Only a 'model not found / removed' signal counts as
    unavailable; any other error is treated as transient (the normal retry path
    handles it) so we don't wrongly skip on a blip."""
    from app.observability import audit

    try:
        provider.complete_json("Reply with a JSON object.", "ping", max_tokens=16)
        return True
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        unavailable = ("404" in msg or "not found" in msg or "does not exist" in msg
                       or "unknown model" in msg or "no such model" in msg
                       or "gone" in msg or "410" in msg)
        if unavailable:
            audit("MODEL_UNAVAILABLE", model=getattr(provider, "model", provider.name),
                  error=str(e)[:200])
            return False
        return True  # transient/other error — not a model-availability problem


def get_chat_provider() -> LlmProvider:
    """Provider used for chat answers. Defaults to the main provider/model but can
    be overridden with CHAT_PROVIDER / CHAT_MODEL (e.g. extract locally, chat on
    Claude)."""
    cfg = get_settings()
    return get_provider(cfg.chat_provider or None, cfg.chat_model or None)


def get_prep_provider() -> LlmProvider:
    """Provider for interview prep generation. Falls back to chat, then main."""
    cfg = get_settings()
    return get_provider(cfg.prep_provider or cfg.chat_provider or None,
                        cfg.prep_model or cfg.chat_model or None)
