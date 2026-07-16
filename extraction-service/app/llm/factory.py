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
