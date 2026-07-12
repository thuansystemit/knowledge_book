import { useState } from 'react';
import type { Difficulty, PrepQuestion } from '../../api/interview-prep.api';

const DIFFICULTY_STYLE: Record<Difficulty, { bg: string; fg: string; label: string }> = {
  easy: { bg: 'rgba(40,167,69,0.12)', fg: '#28a745', label: 'Easy' },
  medium: { bg: 'rgba(255,159,10,0.14)', fg: '#c77700', label: 'Medium' },
  hard: { bg: 'rgba(220,53,69,0.12)', fg: '#dc3545', label: 'Hard' },
};

export function QuestionCard({ q }: { q: PrepQuestion }) {
  const [open, setOpen] = useState(false);
  const d = DIFFICULTY_STYLE[q.difficulty] ?? DIFFICULTY_STYLE.medium;

  return (
    <div className="card mb-2" style={{ border: '1px solid var(--border)' }}>
      <div className="card-body py-3">
        <div className="d-flex align-items-start justify-content-between gap-2">
          <div className="fw-semibold" style={{ color: 'var(--ink)' }}>{q.question}</div>
          <span
            className="badge flex-shrink-0"
            style={{ background: d.bg, color: d.fg, fontWeight: 600 }}
          >
            {d.label}
          </span>
        </div>

        <div className="d-flex align-items-center gap-2 mt-2" style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
          <i className="bi bi-tag" aria-hidden="true" />
          <span>{q.topic}</span>
        </div>

        <button
          type="button"
          className="btn btn-sm btn-outline-secondary mt-2"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          <i className={`bi ${open ? 'bi-chevron-up' : 'bi-chevron-down'} me-1`} aria-hidden="true" />
          {open ? 'Hide model answer' : 'Show model answer'}
        </button>

        {open && (
          <div
            className="mt-2 p-2 rounded"
            style={{ background: 'var(--surface, #faf9f7)', whiteSpace: 'pre-wrap', color: 'var(--ink)' }}
          >
            {q.model_answer}
            {q.citations && q.citations.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem', marginTop: '0.625rem' }}>
                {q.citations.map((c, i) => (
                  <span key={i} className="citation-chip" title={c}>
                    <span className="citation-chip-dot" aria-hidden="true"></span>
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
