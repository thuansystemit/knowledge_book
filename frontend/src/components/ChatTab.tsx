import { useEffect, useRef, useState } from 'react';
import {
  ask, clearHistory, getHistory, subscribeChatStream,
  type ChatMessage, type Citation,
} from '../api/chat.api';
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
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { getHistory(jobId).then((h) => setMessages(h.messages)); }, [jobId]);
  useEffect(() => { scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight); }, [messages, streaming]);

  const send = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    setInput('');
    setError(null);
    setBusy(true);
    setMessages((m) => [...m, { id: `local-${Date.now()}`, role: 'user', content: question }]);
    setStreaming('');
    try {
      const { message_id, stream_token } = await ask(jobId, question);
      let acc = '';
      subscribeChatStream(
        jobId, message_id, stream_token,
        (tok) => { acc += tok; setStreaming(acc); },
        (citations: Citation[]) => {
          setMessages((m) => [...m, { id: `a-${Date.now()}`, role: 'assistant', content: acc, citations }]);
          setStreaming(null);
          setBusy(false);
        },
        (msg) => { setError(msg); setStreaming(null); setBusy(false); },
      );
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'failed to ask');
      setStreaming(null);
      setBusy(false);
    }
  };

  const onClear = async () => {
    if (!confirm('Clear this conversation?')) return;
    await clearHistory(jobId);
    setMessages([]);
  };

  const empty = messages.length === 0 && streaming === null;

  return (
    <div className="chat">
      <div className="chat-log" ref={scrollRef}>
        {empty && (
          <div className="chat-empty">
            <p className="muted">Ask anything about this document — grounded in its knowledge graph.</p>
            <div className="suggests">
              {suggestions(graph).map((s) => (
                <button key={s} className="chip" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.role}`}>
            <div className="bubble-body">{m.content}</div>
            {m.citations && m.citations.length > 0 && (
              <div className="cites">
                {m.citations.map((c, i) => (
                  <span key={i} className="cite" title={c.name}>
                    {c.name}{c.chapter ? ` · ${c.chapter} p.${c.page_start}-${c.page_end}` : ''}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {streaming !== null && (
          <div className="bubble assistant">
            <div className="bubble-body">{streaming || <span className="typing">…</span>}</div>
          </div>
        )}
      </div>

      {error && <p className="err">{error}</p>}

      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input
          value={input}
          placeholder="Ask a question…"
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button className="btn" disabled={busy || !input.trim()}>{busy ? '…' : 'Send'}</button>
        {messages.length > 0 && (
          <button type="button" className="btn-ghost" onClick={onClear} disabled={busy}>Clear</button>
        )}
      </form>
    </div>
  );
}
