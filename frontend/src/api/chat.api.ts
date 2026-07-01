import { api, API_URL } from './client';

export interface Citation {
  node_id: string; name: string;
  chapter: string | null; page_start: number | null; page_end: number | null;
}
export interface ChatMessage {
  id: string; role: 'user' | 'assistant'; content: string;
  citations?: Citation[] | null; model?: string | null; created_at?: string | null;
}

export async function getHistory(jobId: string) {
  const { data } = await api.get<{ session_id: string | null; messages: ChatMessage[] }>(
    `/api/jobs/${jobId}/chat/history`,
  );
  return data;
}

export async function ask(jobId: string, question: string) {
  const { data } = await api.post<{ message_id: string; stream_token: string }>(
    `/api/jobs/${jobId}/chat`,
    { question },
  );
  return data;
}

export async function clearHistory(jobId: string) {
  await api.delete(`/api/jobs/${jobId}/chat`);
}

/** Stream one answer. Returns an unsubscribe fn. */
export function subscribeChatStream(
  jobId: string,
  msgId: string,
  token: string,
  onToken: (t: string) => void,
  onDone: (citations: Citation[]) => void,
  onError: (msg: string) => void,
): () => void {
  const es = new EventSource(
    `${API_URL}/api/jobs/${jobId}/chat/${msgId}/stream?t=${encodeURIComponent(token)}`,
  );
  es.onmessage = (m) => {
    try {
      const d = JSON.parse(m.data);
      if (d.error) onError(d.error);
      else if (d.done) onDone(d.citations || []);
      else if (d.token) onToken(d.token);
    } catch {
      /* ignore malformed frame */
    }
  };
  es.addEventListener('end', () => es.close());
  es.onerror = () => es.close();
  return () => es.close();
}
