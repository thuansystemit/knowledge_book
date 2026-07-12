import { useState } from 'react';
import type { PrepPlanDetail } from '../../api/interview-prep.api';
import { QuestionCard } from './QuestionCard';

type Tab = 'path' | 'checklist' | 'questions';

export function PrepPlanView({ plan }: { plan: PrepPlanDetail }) {
  const [tab, setTab] = useState<Tab>('path');
  const data = plan.plan_data;
  const thin = data?.corpus_coverage.topics_without_coverage ?? [];

  if (!data) {
    return <div className="alert alert-warning">This plan has no generated content yet.</div>;
  }

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: 'path', label: 'Study Path', count: data.study_path.length },
    { id: 'checklist', label: 'Checklist', count: Object.keys(data.checklist).length },
    { id: 'questions', label: 'Practice Questions', count: plan.questions.length },
  ];

  return (
    <div>
      {/* Coverage summary + thin-coverage warning chips */}
      <div className="d-flex flex-wrap align-items-center gap-2 mb-3" style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
        <span><i className="bi bi-folder2-open me-1" aria-hidden="true" />
          {data.corpus_coverage.total_docs_scanned} document(s) scanned</span>
        <span>·</span>
        <span>{data.corpus_coverage.topics_with_coverage} topic(s) well covered</span>
        {thin.length > 0 && (
          <span
            className="badge"
            style={{ background: 'rgba(255,159,10,0.14)', color: '#c77700' }}
            title={`Thin coverage — add documents on: ${thin.join(', ')}`}
          >
            <i className="bi bi-exclamation-triangle me-1" aria-hidden="true" />
            {thin.length} topic(s) thin
          </span>
        )}
      </div>

      {/* Tabs */}
      <ul className="nav nav-tabs mb-3">
        {tabs.map((t) => (
          <li className="nav-item" key={t.id}>
            <button
              className={`nav-link${tab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label} <span className="badge bg-secondary ms-1">{t.count}</span>
            </button>
          </li>
        ))}
      </ul>

      {tab === 'path' && (
        <ol className="list-group list-group-numbered">
          {data.study_path.map((s) => (
            <li key={s.order} className="list-group-item" style={{ border: '1px solid var(--border)' }}>
              <div className="d-flex justify-content-between">
                <span className="fw-semibold" style={{ color: 'var(--ink)' }}>{s.topic}</span>
                {s.time_estimate_hours != null && (
                  <span className="text-muted" style={{ fontSize: '0.8rem' }}>~{s.time_estimate_hours}h</span>
                )}
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>{s.description}</div>
              {s.source_docs.length > 0 && (
                <div className="mt-1" style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                  <i className="bi bi-book me-1" aria-hidden="true" />{s.source_docs.join(', ')}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      {tab === 'checklist' && (
        <div className="d-flex flex-column gap-3">
          {Object.entries(data.checklist).map(([topic, items]) => (
            <div key={topic}>
              <div className="fw-semibold mb-1" style={{ color: 'var(--ink)' }}>{topic}</div>
              <ul className="mb-0">
                {items.map((it, i) => (
                  <li key={i} style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>{it}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {tab === 'questions' && (
        <div>
          {plan.questions.length === 0
            ? <div className="text-muted">No questions generated.</div>
            : plan.questions.map((q) => <QuestionCard key={q.id} q={q} />)}
        </div>
      )}
    </div>
  );
}
