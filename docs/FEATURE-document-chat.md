# Feature: Chat with Document (Knowledge-Graph-Grounded Q&A)

| | |
|---|---|
| **Document** | Feature Spec + Design-as-built |
| **Version** | 1.0 |
| **Date** | 2026-07-01 |
| **Status** | Implemented (MVP) |
| **Parents** | `01-product-spec.md`, `ARCHITECTURE-mvp.md` |
| **Design input** | architect agent brief (grounding-strategy analysis) |

> Lets a logged-in user **chat with a document**, grounded in that document's
> already-extracted **knowledge graph**. Examples: "summarize chapter 1", "what
> does the book say about coupling?", "how does DRY relate to orthogonality?".
> Answers stream token-by-token, cite chapter/page, and don't use anything
> outside the document's graph.

---

## 1. Decisions (locked)

Three product decisions shaped the build (the architect agent laid out the
options; the user chose):

| Decision | Choice | Why |
|---|---|---|
| **Grounding source** | **Graph-only** — answer from the stored nodes/edges/brief/`source_refs`. No embeddings, no chunk-RAG. | We already store the graph and **discarded chunk text**; graph-only ships now, works on every existing document, and needs no new infra. (Also sidesteps the embedding-model dependency.) |
| **Chat model** | **Configurable, default local** — `CHAT_PROVIDER`/`CHAT_MODEL`, default = the main provider (local Ollama `qwen2.5:3b`). | Run extraction locally, point chat at Claude when quality matters — no code change. |
| **Conversation** | **Multi-turn** — persisted history, last N turns fed back. | More natural follow-ups; history capped for the small local context window. |

**Explicitly not built (deferred):** chunk persistence, embeddings/pgvector,
hybrid retrieval (see §9 Future). The MVP is designed so these can be added
later without changing the chat API or UI.

---

## 2. How it works (flow)

```
User types a question in the Chat tab
      │
      ▼
POST /api/jobs/{id}/chat {question}     (Bearer auth; owner|admin; job must be done)
   → saves the user message, returns { message_id, stream_token(60–180s) }
      │
      ▼
GET /api/jobs/{id}/chat/{msg_id}/stream?t=<token>     (SSE; EventSource)
   → build_context(graph, question): pick the relevant graph slice
        - "chapter N" in question → nodes whose source_refs match that chapter
        - else → nodes with keyword overlap vs. name+definition
        - + connecting edges + the brief
   → system prompt = "use ONLY this context, cite chapter/page"
   → messages = last N turns of history (multi-turn)
   → provider.stream_chat(...) yields tokens  →  data: {"token": "..."}
   → on completion: persist assistant message + data: {"done", citations}
```

Streaming reuses the app's proven **stream-token** pattern (EventSource can't
send `Authorization`, so a short-lived signed token rides in `?t=`).

---

## 3. Grounding (`app/chat.py`)

`build_context(graph, question) -> (system_prompt, citations)`:
- **Chapter scoping:** if the question matches `chapter\s+(\d+|roman)`, select
  nodes whose `source_refs.chapter` matches — this is how "summarize chapter 1"
  is answered from the graph.
- **Keyword grounding:** otherwise, score nodes by word overlap between the
  question and each node's `name + definition`; take the top ~20.
- Add connecting **edges** (with their `evidence`) and the **brief** (thesis +
  summary).
- **Citations** = the `source_refs` (concept name + chapter + page range) of the
  grounded nodes, deduped, capped at 12. Returned to the UI at stream end.

**Honesty by design:** the system prompt (`prompts/chat_answer.txt`) instructs
the model to use only the provided context, cite chapter/page, and — for chapter
summaries — note it is synthesising from an extracted graph, not the prose.

---

## 4. Data model

```
chat_sessions   id, job_id (FK jobs ON DELETE CASCADE), user_id, created_at, updated_at
                UNIQUE(job_id, user_id)        -- one thread per user per document
chat_messages   id, session_id (FK ON DELETE CASCADE), role('user'|'assistant'),
                content, citations(JSON), model, created_at
```
Deleting a document (or clearing chat) cascades to its messages. `model` records
which model actually answered (for comparing local vs. Claude quality).

---

## 5. API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/jobs/{id}/chat` | Bearer, owner\|admin | Ask a question → `{message_id, stream_token}` |
| GET | `/api/jobs/{id}/chat/{msg_id}/stream?t=` | chat-stream token | SSE answer stream (`{token}` … `{done, citations}` … `event: end`) |
| GET | `/api/jobs/{id}/chat/history` | Bearer, owner\|admin | Past messages for this doc |
| DELETE | `/api/jobs/{id}/chat` | Bearer, owner\|admin | Clear the conversation |

Ownership is enforced (`job.user_id == user.id or admin`). The `chat-stream`
JWT is scoped to `{sub, job, msg}` and expires in `CHAT_STREAM_TOKEN_TTL_SEC`
(default 180s).

---

## 6. LLM interface

- New protocol method **`stream_chat(system_prompt, messages, max_tokens) -> Iterator[str]`**
  implemented for **Ollama** (`/api/chat` streaming, plain text — not JSON),
  **Claude** (`messages.stream`, no thinking/JSON), **OpenAI** (Chat Completions
  `stream=True`).
- **`get_chat_provider()`** returns the provider/model for chat: `CHAT_PROVIDER`
  / `CHAT_MODEL` if set, else the main `LLM_PROVIDER` / model.

---

## 7. Frontend

- **`ChatTab`** (`components/ChatTab.tsx`) added as a third tab on the document
  page (Brief / Concept graph / **Chat**).
- Loads history, renders a message log with user/assistant bubbles, **streams
  the assistant answer token-by-token**, shows **citation chips**
  (concept · chapter/page), offers **suggested starter questions** derived from
  the brief/graph, and supports **Clear**.
- **`api/chat.api.ts`**: `ask`, `subscribeChatStream` (EventSource), `getHistory`,
  `clearHistory`.

---

## 8. Configuration (env)

| Var | Default | Meaning |
|---|---|---|
| `CHAT_PROVIDER` | (main `LLM_PROVIDER`) | Provider for chat answers (`ollama`\|`claude`\|`openai`) |
| `CHAT_MODEL` | (provider default) | Model override for chat |
| `CHAT_HISTORY_TURNS` | 8 | Prior messages fed back for multi-turn |
| `CHAT_STREAM_TOKEN_TTL_SEC` | 180 | SSE token lifetime |

Run extraction locally but chat on Claude: `CHAT_PROVIDER=claude` +
`ANTHROPIC_API_KEY` (no restart of extraction needed).

---

## 9. Limitations & risks

- **No prose fidelity.** Graph-only means "summarize chapter N" is a *synthesis
  of the concepts tagged to that chapter*, not the original narrative — we don't
  store the source text. Verbatim quotes and minor points not promoted to nodes
  are unavailable.
- **Small-model quality.** `qwen2.5:3b` follows "use only this context" less
  reliably than Claude; for production-grade grounding, set `CHAT_PROVIDER=claude`.
- **Runtime dependency.** Chat needs the configured LLM reachable. The local
  Ollama host must be up; if it's unreachable the stream returns an error event
  (surfaced in the UI) rather than hanging.
- **Single-process.** Streams run in the request/threadpool; fine at current
  scale. Multi-worker durability (Redis) is out of scope, consistent with the
  rest of the app.

---

## 10. Future (Phase 2 — hybrid RAG upgrade path)

The MVP is deliberately upgrade-compatible. To add prose-level grounding later
(no chat-API/UI change):
1. Persist chunk text during extraction (`document_chunks` table).
2. Add embeddings (Ollama `nomic-embed-text` / OpenAI) + **pgvector** on the
   existing Postgres.
3. `build_context` retrieves chapter-scoped chunks via vector search and adds
   them to the prompt; falls back to graph-only for documents without chunks.

---

## 11. Files

| File | Change |
|---|---|
| `app/llm/provider.py` | `stream_chat` on the protocol |
| `app/llm/{ollama,claude,openai}_provider.py` | `stream_chat` implementations |
| `app/llm/factory.py` | `get_provider(model=…)`, `get_chat_provider()` |
| `app/config.py` | `chat_provider`, `chat_model`, `chat_history_turns`, `chat_stream_token_ttl_sec` |
| `app/models.py` | `ChatSession`, `ChatMessage` |
| `app/security.py` | `make_chat_stream` |
| `app/chat.py` (new) | `build_context` (graph grounding + citations) |
| `app/chat_routes.py` (new) | ask / stream / history / clear |
| `app/api.py` | include `chat_router` |
| `app/prompts/chat_answer.txt` (new) | grounded-answer system prompt |
| `frontend/src/api/chat.api.ts` (new) | chat client |
| `frontend/src/components/ChatTab.tsx` (new) | Chat tab UI |
| `frontend/src/routes/DocumentDetailPage.tsx` | add Chat tab |

---

*End of Feature Spec v1.0.*
