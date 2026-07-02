import { useEffect, useRef, useState } from 'react';
import {
  ask, clearHistory, getHistory, subscribeChatStream,
  type ChatMessage, type Citation,
} from '../api/chat.api';
import { getModels, type ModelOption } from '../api/models.api';
import type { Graph } from '../api/jobs.api';

function suggestions(graph: Graph): string[] {
  const out: string[] = [];
  if (graph.brief?.thesis) out.push('What is the main thesis of this book?');
  graph.nodes.slice(0, 2).forEach((n) => out.push(`Explain "${n.name}".`));
  const e = graph.edges[0];
  if (e) out.push(`How does "${e.source}" relate to "${e.target}"?`);
  out.push('Summarize chapter 1.');
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
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { getHistory(jobId).then((h) => setMessages(h.messages)); }, [jobId]);
  useEffect(() => {
    getModels().then((m) => { setModels(m.models); setModel(m.default_chat_model); }).catch(() => {});
  }, []);
  useEffect(() => { scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight); }, [messages, streaming]);

  const send = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    setInput(''); setError(null); setBusy(true);
    setMessages((m) => [...m, { id: `local-${Date.now()}`, role: 'user', content: question }]);
    setStreaming('');
    try {
      const { message_id, stream_token } = await ask(jobId, question, model || undefined);
      let acc = '';
      subscribeChatStream(jobId, message_id, stream_token,
        (tok) => { acc += tok; setStreaming(acc); },
        (citations: Citation[]) => {
          setMessages((m) => [...m, { id: `a-${Date.now()}`, role: 'assistant', content: acc, citations }]);
          setStreaming(null); setBusy(false);
        },
        (msg) => { setError(msg); setStreaming(null); setBusy(false); });
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'failed to ask');
      setStreaming(null); setBusy(false);
    }
  };

  const onClear = async () => {
    if (!confirm('Clear this conversation?')) return;
    await clearHistory(jobId);
    setMessages([]);
  };

  const empty = messages.length === 0 && streaming === null;

  return (
    <div className="d-flex flex-column">
      <div className="chat-log d-flex flex-column gap-3 mb-3" ref={scrollRef}>
        {empty && (
          <div className="my-auto">
            <p className="text-secondary">Ask anything about this document — grounded in its knowledge graph.</p>
            <div className="d-flex flex-wrap gap-2">
              {suggestions(graph).map((s) => (
                <button key={s} className="btn btn-sm btn-outline-secondary rounded-pill" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.role} ${m.role === 'user' ? 'align-self-end' : 'align-self-start'}`}>
            <div>{m.content}</div>
            {m.citations && m.citations.length > 0 && (
              <div className="d-flex flex-wrap gap-1 mt-2">
                {m.citations.map((c, i) => (
                  <span key={i} className="badge text-bg-light border" title={c.name}>
                    {c.name}{c.chapter ? ` · ${c.chapter} p.${c.page_start}-${c.page_end}` : ''}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {streaming !== null && (
          <div className="bubble assistant align-self-start">
            <div>{streaming || <span className="typing">…</span>}</div>
          </div>
        )}
      </div>

      {error && <div className="alert alert-danger py-2 small">{error}</div>}

      <form className="d-flex gap-2" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        {models.length > 0 && (
          <select className="form-select flex-shrink-0" style={{ width: 200 }} value={model}
            onChange={(e) => setModel(e.target.value)} disabled={busy} title="Answer model">
            {models.map((m) => <option key={m.model_id} value={m.model_id}>{m.label}</option>)}
          </select>
        )}
        <input className="form-control" value={input} placeholder="Ask a question…"
          onChange={(e) => setInput(e.target.value)} disabled={busy} />
        <button className="btn btn-primary" disabled={busy || !input.trim()}>
          {busy ? '…' : <><i className="bi bi-send me-1"></i>Send</>}
        </button>
        {messages.length > 0 && (
          <button type="button" className="btn btn-outline-secondary" onClick={onClear} disabled={busy}>Clear</button>
        )}
      </form>
    </div>
  );
}
