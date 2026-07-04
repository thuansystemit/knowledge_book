import { useEffect, useRef, useState } from 'react';
import {
  ask, clearHistory, getHistory, subscribeChatStream,
  type ChatMessage, type Citation,
} from '../api/chat.api';
import { getModels, type ModelOption } from '../api/models.api';
import type { Graph } from '../api/jobs.api';
import { getApiError } from '../lib/utils';
import { Select } from './Select';
import { ConfirmDialog } from './ConfirmDialog';

function suggestions(graph: Graph): string[] {
  const out: string[] = [];
  if (graph.brief?.thesis) out.push('What is the main thesis of this document?');
  graph.nodes.slice(0, 2).forEach((n) => out.push(`Explain "${n.name}".`));
  const e = graph.edges[0];
  if (e) out.push(`How does "${e.source}" relate to "${e.target}"?`);
  out.push('Summarise chapter 1.');
  return out.slice(0, 4);
}

export function ChatTab({ jobId, graph }: { jobId: string; graph: Graph }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState<string>('');
  // 'retrieval' answers come from the extracted graph with no LLM, so the
  // per-answer model picker is hidden.
  const [chatMode, setChatMode] = useState<string>('');
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const [clearBusy, setClearBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { getHistory(jobId).then((h) => setMessages(h.messages)); }, [jobId]);
  useEffect(() => {
    getModels()
      .then((m) => { setModels(m.models); setModel(m.default_chat_model); setChatMode(m.chat_mode ?? 'llm'); })
      .catch(() => {});
  }, []);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streaming]);

  const send = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    setInput('');
    setError(null);
    setBusy(true);
    setMessages((m) => [...m, { id: `local-${Date.now()}`, role: 'user', content: question }]);
    setStreaming('');
    try {
      const { message_id, stream_token } = await ask(jobId, question, model || undefined);
      let acc = '';
      subscribeChatStream(
        jobId, message_id, stream_token,
        (tok) => { acc += tok; setStreaming(acc); },
        (citations: Citation[]) => {
          setMessages((m) => [
            ...m,
            { id: `a-${Date.now()}`, role: 'assistant', content: acc, citations },
          ]);
          setStreaming(null);
          setBusy(false);
        },
        (msg) => { setError(msg); setStreaming(null); setBusy(false); },
      );
    } catch (err: unknown) {
      setError(getApiError(err, 'failed to ask'));
      setStreaming(null);
      setBusy(false);
    }
  };

  /** Opens the confirm dialog — the actual clearing runs in confirmClear. */
  const onClearClick = () => setClearDialogOpen(true);

  const confirmClear = async () => {
    setClearBusy(true);
    try {
      await clearHistory(jobId);
      setMessages([]);
      setClearDialogOpen(false);
    } catch (err: unknown) {
      setClearDialogOpen(false);
      setError(getApiError(err, 'Failed to clear chat history'));
    } finally {
      setClearBusy(false);
    }
  };

  const empty = messages.length === 0 && streaming === null;

  return (
    <div className="d-flex flex-column">
      {/* ── Chat log ── */}
      <div className="chat-log" ref={scrollRef}>
        {empty && (
          <div style={{ marginTop: 'auto', paddingTop: '0.5rem' }}>
            <p style={{ fontSize: '0.875rem', color: 'var(--muted)', marginBottom: '0.875rem' }}>
              Ask anything about this document — grounded in its knowledge graph.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {suggestions(graph).map((s) => (
                <button key={s} className="chat-suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`bubble ${m.role}`}
            style={m.role === 'user' ? { alignSelf: 'flex-end' } : { alignSelf: 'flex-start' }}
          >
            <div>{m.content}</div>
            {/* Citation chips — white bg, terracotta dot + text */}
            {m.citations && m.citations.length > 0 && (
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '0.375rem',
                  marginTop: '0.625rem',
                }}
              >
                {m.citations.map((c, i) => (
                  <span key={i} className="citation-chip" title={c.name}>
                    <span className="citation-chip-dot" aria-hidden="true"></span>
                    {c.name}
                    {c.chapter ? ` · ${c.chapter} p.${c.page_start}` : ''}
                  </span>
                ))}
              </div>
            )}
            {/* Answer provenance (RC-21): tell the user whether the answer was
                composed straight from the document (no AI) or generated by an LLM. */}
            {m.role === 'assistant' && (() => {
              const isRetrieval = m.model ? m.model.startsWith('retrieval') : chatMode === 'retrieval';
              return (
                <div
                  className="d-flex align-items-center gap-1"
                  style={{ marginTop: '0.55rem', fontSize: '0.7rem', color: 'var(--muted)' }}
                  title={isRetrieval
                    ? 'Composed directly from the document — no AI text generation'
                    : 'Generated by an AI model, grounded in the document'}
                >
                  <i className={`bi ${isRetrieval ? 'bi-file-earmark-text' : 'bi-stars'}`} aria-hidden="true" />
                  {isRetrieval ? 'Answered from the document · no AI generation' : `AI-generated${m.model ? ` · ${m.model}` : ''}`}
                </div>
              );
            })()}
          </div>
        ))}

        {streaming !== null && (
          <div className="bubble assistant" style={{ alignSelf: 'flex-start' }}>
            <div>{streaming || <span className="typing">Thinking…</span>}</div>
          </div>
        )}
      </div>

      {error && (
        <div className="alert alert-danger mb-2" role="alert">
          <i className="bi bi-exclamation-circle me-2"></i>
          {error}
        </div>
      )}

      {/* ── Input row — pill-shaped ── */}
      <form
        className="d-flex gap-2 mt-2"
        onSubmit={(e) => { e.preventDefault(); send(input); }}
      >
        {chatMode !== 'retrieval' && models.length > 0 && (
          <Select
            value={model}
            onChange={setModel}
            options={models.map((m) => ({ value: m.model_id, label: m.label }))}
            disabled={busy}
            width={180}
            ariaLabel="Answer model"
            className="flex-shrink-0"
          />
        )}

        {/* Pill-shaped text input */}
        <input
          className="form-control chat-input-pill"
          value={input}
          placeholder="Ask a question…"
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          aria-label="Your question"
        />

        {/* Terracotta Send pill */}
        <button
          type="submit"
          className="btn btn-primary flex-shrink-0"
          disabled={busy || !input.trim()}
          aria-label="Send"
        >
          {busy ? (
            <span
              className="spinner-border spinner-border-sm"
              role="status"
              aria-hidden="true"
            ></span>
          ) : (
            'Send'
          )}
        </button>

        {messages.length > 0 && (
          <button
            type="button"
            className="btn btn-outline-secondary flex-shrink-0"
            onClick={onClearClick}
            disabled={busy || clearBusy}
          >
            Clear
          </button>
        )}
      </form>

      <ConfirmDialog
        open={clearDialogOpen}
        title="Clear chat?"
        message="All messages in this conversation will be permanently removed."
        confirmLabel="Clear"
        danger
        busy={clearBusy}
        onConfirm={confirmClear}
        onCancel={() => setClearDialogOpen(false)}
      />
    </div>
  );
}
