import { APP_NAME } from '../../lib/constants';

export function AboutPage() {
  return (
    <div style={{ maxWidth: 720 }}>
      <h1 className="page-title">About {APP_NAME}</h1>
      <p className="page-subtitle" style={{ marginBottom: '1.75rem' }}>
        Turning dense technical documents into navigable knowledge.
      </p>

      <div className="card mb-4">
        <div className="card-body">
          <p style={{ marginBottom: '1rem' }}>
            {APP_NAME} is an internal knowledge-management platform designed for teams that need to
            extract insight from large volumes of technical documents — PDFs, scanned reports, and
            multi-chapter references. Rather than leaving documents as opaque files, {APP_NAME}{' '}
            processes each upload through an asynchronous extraction pipeline and produces four
            structured outputs you can browse, search, and query.
          </p>
          <p style={{ marginBottom: 0 }}>
            Role-based access control keeps sensitive material in the right hands: admins manage
            users and configure the extraction pipeline; editors can upload and annotate; viewers
            can read, search, and query — but not upload. Categories let administrators partition
            the document library and grant per-category permissions so different teams only see
            what is relevant to them.
          </p>
        </div>
      </div>

      <div className="card mb-4">
        <div className="card-header">
          <h2 className="section-heading" style={{ fontSize: '0.9375rem' }}>
            What the pipeline produces
          </h2>
        </div>
        <div className="card-body">
          <ul
            style={{
              margin: 0,
              paddingLeft: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              color: 'var(--body)',
              fontSize: '0.875rem',
              lineHeight: 1.6,
            }}
          >
            <li>
              <strong style={{ color: 'var(--ink)' }}>Brief</strong> — a concise executive
              summary of the document's purpose, scope, and key findings, generated during
              extraction.
            </li>
            <li>
              <strong style={{ color: 'var(--ink)' }}>Concept graph</strong> — an interactive
              node-link diagram of the concepts and relationships identified in the document,
              backed by a property graph stored in the database.
            </li>
            <li>
              <strong style={{ color: 'var(--ink)' }}>Chapter guide</strong> — a structured
              outline of the document's sections with short summaries, making long documents
              navigable without reading every page.
            </li>
            <li>
              <strong style={{ color: 'var(--ink)' }}>Document Q&amp;A</strong> — a
              retrieval-augmented chat interface that answers questions grounded in the document's
              own text; every answer is traceable back to the source passage.
            </li>
          </ul>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="section-heading" style={{ fontSize: '0.9375rem' }}>
            Technology stack
          </h2>
        </div>
        <div className="card-body">
          <p style={{ marginBottom: 0, color: 'var(--muted)', fontSize: '0.875rem', lineHeight: 1.6 }}>
            The frontend is a Vite + React SPA. The backend is a FastAPI service backed by
            PostgreSQL and Redis, with long-running extraction tasks dispatched via Celery
            workers. OCR for scanned PDFs is handled during the extraction stage before text is
            passed to a configurable LLM provider for concept and summary generation.
          </p>
        </div>
      </div>
    </div>
  );
}
