"""Environment-driven settings for the knowledge-graph extraction service.

Mirrors the toeic_app extraction-service pattern: LLM provider/model/key are all
.env-driven and LIVE (re-read on demand via get_settings()), so switching from
Claude to OpenAI to a local Ollama model needs no code change or rebuild."""
import os
from dataclasses import dataclass, field

ENV_FILE = os.environ.get("ENV_FILE", "/app/.env")


def _load_env_file(path: str) -> None:
    """Read a KEY=VALUE .env into os.environ. Dependency-free: skips blanks and
    `#` comments, strips surrounding quotes. Missing file is fine."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if key:
                    os.environ[key] = val.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass


@dataclass(frozen=True)
class Settings:
    # LLM provider selection + per-provider config (all live-switchable via .env).
    # Default is the LOCAL ollama provider — no API key, runs offline. Switch to
    # claude/openai via .env once you want cloud quality.
    provider: str = field(default_factory=lambda: os.environ.get("LLM_PROVIDER", "ollama"))

    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8"))

    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-4o"))
    # Optional base URL for any OpenAI-compatible endpoint (NVIDIA NIM, Together,
    # Groq, a local vLLM, …). Blank = the real OpenAI API. e.g.
    # https://integrate.api.nvidia.com/v1 with OPENAI_MODEL=z-ai/glm-5.2
    openai_base_url: str = field(default_factory=lambda: os.environ.get("OPENAI_BASE_URL", "").strip())

    ollama_base_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://192.168.100.158:11434"))
    ollama_model: str = field(default_factory=lambda: os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"))

    # Ingestion guardrails (PRD §6, §FR-0.1).
    max_file_bytes: int = field(default_factory=lambda: int(os.environ.get("MAX_FILE_BYTES", str(100 * 1024 * 1024))))
    max_pages: int = field(default_factory=lambda: int(os.environ.get("MAX_PAGES", "500")))
    min_chars: int = field(default_factory=lambda: int(os.environ.get("MIN_TEXT_CHARS", "40")))
    # OCR quality gate (ING-06): mean Tesseract word confidence (0-100) below this
    # flags the document low_confidence so the UI warns the reader.
    ocr_min_confidence: float = field(default_factory=lambda: float(os.environ.get("OCR_MIN_CONFIDENCE", "70")))
    # Layout parsing (HAR-01/02): column-aware extraction for 2-column PDFs and
    # figure/table caption extraction. Both fall back safely if disabled.
    layout_columns: bool = field(default_factory=lambda: os.environ.get("LAYOUT_COLUMNS", "true").lower() in ("1", "true", "yes"))
    extract_captions: bool = field(default_factory=lambda: os.environ.get("EXTRACT_CAPTIONS", "true").lower() in ("1", "true", "yes"))

    # Chunking (prose section-level; token estimate).
    chunk_tokens: int = field(default_factory=lambda: int(os.environ.get("CHUNK_TOKENS", "1200")))
    chunk_overlap: int = field(default_factory=lambda: int(os.environ.get("CHUNK_OVERLAP", "150")))
    # Extra attempts per chunk when the model returns unparseable output (small
    # local models occasionally do). 2 -> up to 3 tries before giving up.
    chunk_retries: int = field(default_factory=lambda: int(os.environ.get("CHUNK_RETRIES", "2")))
    # Inter-chunk throttle (ms) before each extraction LLM call — paces requests
    # under provider rate limits (e.g. NVIDIA free tier). 0 = no throttle.
    chunk_throttle_ms: int = field(default_factory=lambda: int(os.environ.get("CHUNK_THROTTLE_MS", "0")))
    # SDK-level retry count for cloud providers (429/5xx; respects Retry-After).
    llm_max_retries: int = field(default_factory=lambda: int(os.environ.get("LLM_MAX_RETRIES", "5")))
    # Parallel chunk extraction fan-out (EXT-04 / HAR-03 latency). 1 = sequential
    # (default, safe). Raise for providers that allow concurrent requests to cut
    # end-to-end time; keep low (or 1) for rate-limited/free tiers.
    extract_concurrency: int = field(default_factory=lambda: int(os.environ.get("EXTRACT_CONCURRENCY", "1")))
    # Per-document hard cost cap in USD (EXT-02). If accrued LLM cost exceeds this
    # mid-pipeline, the job aborts with FAILED(cost_cap) before overrunning. 0 =
    # disabled. Local/free models never accrue cost, so this never trips them.
    max_doc_cost_usd: float = field(default_factory=lambda: float(os.environ.get("MAX_DOC_COST_USD", "2.0")))
    # Idempotent chunk-extraction cache (EXT-03): reuse a chunk's result on
    # re-process/retry instead of re-calling the LLM. Redis-backed, fail-open.
    chunk_cache_enabled: bool = field(default_factory=lambda: os.environ.get("CHUNK_CACHE_ENABLED", "true").lower() in ("1", "true", "yes"))
    chunk_cache_ttl_days: int = field(default_factory=lambda: int(os.environ.get("CHUNK_CACHE_TTL_DAYS", "30")))

    # --- Semantic retrieval embeddings (RC-14) ------------------------------
    # OFF by default (blank model) -> retrieval stays lexical (RC-11/13), nothing
    # changes. Set EMBEDDING_MODEL to enable: concepts+chunks are embedded at
    # extraction and the chat matches the question vector semantically. Uses an
    # *embedding* model (no generative LLM), via the same provider hosts.
    embedding_model: str = field(default_factory=lambda: os.environ.get("EMBEDDING_MODEL", "").strip())
    embedding_provider: str = field(default_factory=lambda: os.environ.get("EMBEDDING_PROVIDER", "ollama").strip().lower())
    embedding_sim_threshold: float = field(default_factory=lambda: float(os.environ.get("EMBEDDING_SIM_THRESHOLD", "0.55")))

    # Outputs
    output_dir: str = field(default_factory=lambda: os.environ.get("OUTPUT_DIR", "/out"))
    generate_brief: bool = field(default_factory=lambda: os.environ.get("GENERATE_BRIEF", "true").lower() in ("1", "true", "yes"))

    # --- Auth + persistence (Sprint 1a) -------------------------------------
    database_url: str = field(default_factory=lambda: os.environ.get(
        "DATABASE_URL", "postgresql+psycopg2://kb:kb@db:5432/kb"))
    # Redis (enterprise backbone: Celery, SSE pub/sub, config cache).
    redis_url: str = field(default_factory=lambda: os.environ.get(
        "REDIS_URL", "redis://redis:6379/0"))
    # Rate limits per user (0 = disabled). Redis-backed, works across replicas.
    rate_upload_per_hour: int = field(default_factory=lambda: int(os.environ.get("RATE_UPLOAD_PER_HOUR", "30")))
    rate_chat_per_min: int = field(default_factory=lambda: int(os.environ.get("RATE_CHAT_PER_MIN", "20")))

    # --- Subscription plans (monetization-pricing.md; PAY-01/02/03) ----------
    # Monthly document quota per consumer plan (0 = unlimited). Enforced per
    # calendar month, per user. Admins are exempt (super-user). Env-tunable so
    # pricing experiments need no code change.
    plan_free_docs: int = field(default_factory=lambda: int(os.environ.get("PLAN_FREE_DOCS", "2")))
    plan_pro_docs: int = field(default_factory=lambda: int(os.environ.get("PLAN_PRO_DOCS", "20")))
    plan_scholar_docs: int = field(default_factory=lambda: int(os.environ.get("PLAN_SCHOLAR_DOCS", "60")))
    # Concept-map cap on the Free tier (0 = uncapped). Applied at serving time,
    # so an upgrade instantly reveals the full map with no reprocessing (PAY-01).
    plan_free_concepts: int = field(default_factory=lambda: int(os.environ.get("PLAN_FREE_CONCEPTS", "10")))

    # --- Stripe billing (PAY-04) --------------------------------------------
    # All optional: if the secret key is blank, billing endpoints return 503 and
    # the app still boots (on-prem/enterprise deploys need no Stripe). Price IDs
    # come from the Stripe dashboard; map (plan, interval) -> price.
    stripe_secret_key: str = field(default_factory=lambda: os.environ.get("STRIPE_SECRET_KEY", ""))
    stripe_webhook_secret: str = field(default_factory=lambda: os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
    stripe_price_pro_monthly: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_PRO_MONTHLY", ""))
    stripe_price_pro_annual: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_PRO_ANNUAL", ""))
    stripe_price_scholar_monthly: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_SCHOLAR_MONTHLY", ""))
    stripe_price_scholar_annual: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_SCHOLAR_ANNUAL", ""))
    # One-time credit packs (PAY-05): non-expiring extra documents.
    stripe_price_credits_5: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_CREDITS_5", ""))
    stripe_price_credits_10: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_CREDITS_10", ""))
    # Where Stripe redirects after checkout (success/cancel) — the SPA origin.
    frontend_base_url: str = field(default_factory=lambda: os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173"))
    jwt_secret: str = field(default_factory=lambda: os.environ.get("JWT_SECRET", "dev-secret-change-me"))
    access_ttl_min: int = field(default_factory=lambda: int(os.environ.get("ACCESS_TTL_MIN", "15")))
    refresh_ttl_days: int = field(default_factory=lambda: int(os.environ.get("REFRESH_TTL_DAYS", "7")))
    stream_token_ttl_sec: int = field(default_factory=lambda: int(os.environ.get("STREAM_TOKEN_TTL_SEC", "60")))
    # Refresh cookie flags. Secure=false for local http; set true behind HTTPS.
    cookie_secure: bool = field(default_factory=lambda: os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes"))
    cookie_samesite: str = field(default_factory=lambda: os.environ.get("COOKIE_SAMESITE", "lax"))
    # First-admin bootstrap (only used when the users table is empty).
    admin_email: str = field(default_factory=lambda: os.environ.get("ADMIN_EMAIL", "admin@knowledgebook.local"))
    admin_password: str = field(default_factory=lambda: os.environ.get("ADMIN_PASSWORD", "admin12345"))

    # --- Chat (graph-grounded Q&A) ------------------------------------------
    # Which provider/model answers chat. Empty -> use the main LLM_PROVIDER/model.
    # Lets you run extraction locally but chat on Claude, for example.
    chat_provider: str = field(default_factory=lambda: os.environ.get("CHAT_PROVIDER", ""))
    chat_model: str = field(default_factory=lambda: os.environ.get("CHAT_MODEL", ""))
    chat_stream_token_ttl_sec: int = field(default_factory=lambda: int(os.environ.get("CHAT_STREAM_TOKEN_TTL_SEC", "180")))
    # Multi-turn: how many prior messages to include as history (kept small for
    # the local model's context window).
    chat_history_turns: int = field(default_factory=lambda: int(os.environ.get("CHAT_HISTORY_TURNS", "8")))
    # How chat answers a question:
    #   "retrieval" (default) — no query-time LLM; answers are composed
    #        deterministically from the extracted graph (see chat.compose_answer).
    #   "llm" — stream a generated answer from the configured chat model.
    chat_mode: str = field(default_factory=lambda: os.environ.get("CHAT_MODE", "retrieval").strip().lower())
    # Value ladder (RC-20): the minimum consumer plan that gets LLM-synthesized
    # chat when CHAT_MODE=llm. Free users below this get zero-LLM retrieval chat.
    # Admins always get LLM. On-prem/enterprise: set to "free" to give everyone
    # LLM chat regardless of plan.
    chat_llm_min_plan: str = field(default_factory=lambda: os.environ.get("CHAT_LLM_MIN_PLAN", "pro").strip().lower())
    # Retrieval-mode answers are computed instantly; stream them word-by-word with
    # this delay (ms) for a natural "typing" effect like ChatGPT/Claude. 0 = send
    # the whole answer at once (RC-21-adjacent UX).
    retrieval_stream_delay_ms: int = field(default_factory=lambda: int(os.environ.get("RETRIEVAL_STREAM_DELAY_MS", "18")))


def get_settings() -> Settings:
    """Fresh settings after re-reading the mounted .env."""
    _load_env_file(ENV_FILE)
    return Settings()
