# CTX: Chat with Document (graph-grounded Q&A)

> **AI digest of `FEATURE-document-chat.md`. Self-contained — read this alone.**
> Status: implemented MVP (2026-07-01). Convention: paired `*.ctx.md`; keep in sync; work inline.

## What
Logged-in user chats with a document, grounded in that document's **knowledge graph** (nodes/edges/brief/source_refs). e.g. "summarize chapter 1", "how does DRY relate to orthogonality?". Streams tokens, cites chapter/page, multi-turn.

## Locked decisions
- **Graph-only grounding** (no embeddings/RAG/chunk text — we discarded chunks; graph-only works on all existing docs, no new infra).
- **Configurable chat model, default local** — `CHAT_PROVIDER`/`CHAT_MODEL`, default = main provider (Ollama `qwen2.5:3b`); point at Claude anytime.
- **Multi-turn** — persisted history, last `CHAT_HISTORY_TURNS`(8) fed back.
- Deferred: chunk persistence, pgvector, hybrid RAG — MVP designed to add these later with NO chat-API/UI change.

## Flow
POST `/api/jobs/{id}/chat {question}` (Bearer, owner|admin, job done) → saves user msg, returns `{message_id, stream_token}` → GET `/api/jobs/{id}/chat/{msg_id}/stream?t=<token>` (SSE; EventSource can't send auth header so token in `?t=`) → `build_context(graph,question)` → `provider.stream_chat(system, history)` yields `data:{token}` … `data:{done,citations}` … `event:end`. Assistant msg persisted at end.

## Grounding (`app/chat.py build_context`)
- "chapter N" in question → nodes whose `source_refs.chapter` matches (this is how chapter-summary works from graph).
- else → keyword overlap (question words vs node name+definition), top ~20.
- + connecting edges (with evidence) + brief (thesis+summary).
- system prompt (`prompts/chat_answer.txt`): use ONLY provided context, cite chapter/page, note chapter summaries are graph synthesis not prose.
- citations = grounded nodes' source_refs (name+chapter+pages), deduped, ≤12.

## Data model
`chat_sessions(id, job_id FK CASCADE, user_id, timestamps, UNIQUE(job_id,user_id))` — one thread per user per doc. `chat_messages(id, session_id FK CASCADE, role user|assistant, content, citations JSON, model, created_at)`.

## API (all owner|admin)
POST `/api/jobs/{id}/chat` · GET `/api/jobs/{id}/chat/{msg}/stream?t=` (chat-stream JWT scoped {sub,job,msg}, TTL `CHAT_STREAM_TOKEN_TTL_SEC`=180s) · GET `/api/jobs/{id}/chat/history` · DELETE `/api/jobs/{id}/chat`.

## LLM interface
`stream_chat(system_prompt, messages, max_tokens)->Iterator[str]` on Ollama (/api/chat stream, plain text not JSON), Claude (messages.stream, no thinking), OpenAI (stream=True). `get_chat_provider()` = CHAT_PROVIDER/CHAT_MODEL or main provider.

## Frontend
`ChatTab` = 3rd tab (Brief/Graph/**Chat**). Streams answer token-by-token, citation chips (concept·chapter/page), suggested starters from brief/graph, Clear. `api/chat.api.ts`: ask/subscribeChatStream(EventSource)/getHistory/clearHistory.

## Config (env)
CHAT_PROVIDER (default main) · CHAT_MODEL · CHAT_HISTORY_TURNS=8 · CHAT_STREAM_TOKEN_TTL_SEC=180. Run local extract + Claude chat: CHAT_PROVIDER=claude + ANTHROPIC_API_KEY.

## Limits/risks
No prose fidelity (chapter summary = concept synthesis, not narrative; no verbatim quotes). qwen2.5:3b weaker at "use only context" → set CHAT_PROVIDER=claude for quality. Needs LLM reachable — if Ollama host down, stream returns error event (UI shows it), doesn't hang. Single-process.

## Runtime note
Local Ollama host `192.168.100.158` was unreachable after a multi-day machine sleep — extraction+local-chat both need it up. Alternative: CHAT_PROVIDER=claude.

## Files
llm/provider+3 providers (stream_chat), llm/factory (get_chat_provider), config, models (ChatSession/ChatMessage), security (make_chat_stream), chat.py(new), chat_routes.py(new), api.py(include), prompts/chat_answer.txt(new); frontend api/chat.api.ts(new), components/ChatTab.tsx(new), DocumentDetailPage(tab).
