import { APP_NAME } from '../../lib/constants';

/* ─────────────────────────────────────────────────────────────────────────
   TEMPLATE NOTICE
   This is a placeholder privacy policy. It has not been reviewed by legal
   counsel and must not be treated as legal advice or a binding commitment.
   Replace with a policy reviewed by qualified legal professionals before
   any production deployment.
   ───────────────────────────────────────────────────────────────────────── */

const CONTACT_EMAIL = 'privacy@example.com'; // TODO: replace with real address

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} style={{ marginBottom: '1.75rem' }}>
      <h2
        id={id}
        className="section-heading"
        style={{ fontSize: '1rem', marginBottom: '0.625rem' }}
      >
        {title}
      </h2>
      <div style={{ fontSize: '0.875rem', lineHeight: 1.7, color: 'var(--body)' }}>
        {children}
      </div>
    </section>
  );
}

export function PrivacyPage() {
  return (
    <div style={{ maxWidth: 720 }}>
      <h1 className="page-title">Privacy Policy</h1>
      <p className="page-subtitle" style={{ marginBottom: '0.75rem' }}>
        Last updated: 1 July 2026
      </p>

      <div className="alert alert-secondary mb-4" role="note">
        <strong>Template notice:</strong> This is a placeholder privacy policy provided for
        informational purposes only. It has not been reviewed by legal counsel and should not be
        treated as legal advice or a binding commitment. Replace this content with a policy
        reviewed by qualified legal professionals before deployment. Contact details and company
        information marked with <em>TODO</em> must be filled in before this policy is published.
      </div>

      <div className="card">
        <div className="card-body" style={{ padding: '1.5rem 1.75rem' }}>
          <p style={{ fontSize: '0.875rem', lineHeight: 1.7, color: 'var(--body)', marginBottom: '1.75rem' }}>
            {APP_NAME} ("we", "our", or "us") is committed to protecting the personal information
            of the people who use this platform. This policy explains what data we collect, how
            we use it, and the choices you have.
          </p>

          <Section id="data-collected" title="1. Data we collect">
            <p>We collect the following categories of information:</p>
            <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              <li>
                <strong style={{ color: 'var(--ink)' }}>Account information</strong> — name,
                email address, and role assigned by an administrator at the time your account is
                created.
              </li>
              <li>
                <strong style={{ color: 'var(--ink)' }}>Uploaded documents</strong> — any PDF
                or other files you submit through the platform, along with associated metadata
                (filename, upload timestamp, category).
              </li>
              <li>
                <strong style={{ color: 'var(--ink)' }}>Usage data</strong> — pages visited
                within the application, searches performed, and queries submitted to the
                document Q&amp;A interface.
              </li>
              <li>
                <strong style={{ color: 'var(--ink)' }}>Technical data</strong> — IP address,
                browser type, and session tokens needed to keep you signed in.
              </li>
            </ul>
          </Section>

          <Section id="how-used" title="2. How we use your data">
            <p>We use the data listed above to:</p>
            <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              <li>Authenticate you and enforce role-based access controls.</li>
              <li>Process uploaded documents through the extraction pipeline.</li>
              <li>Surface document summaries, concept graphs, and Q&amp;A results.</li>
              <li>Investigate and resolve reported issues.</li>
              <li>Improve the accuracy and performance of the extraction pipeline.</li>
            </ul>
            <p style={{ marginTop: '0.75rem' }}>
              We do not sell, rent, or trade your personal information to third parties for
              marketing purposes.
            </p>
          </Section>

          <Section id="llm-processing" title="3. Third-party LLM processing">
            <p>
              Document text extracted during processing may be sent to a configured external LLM
              provider (for example, a commercial language-model API) to generate summaries,
              concept labels, and relationship descriptions. The specific provider is set by the
              platform administrator in the system configuration.
            </p>
            <p style={{ marginTop: '0.75rem' }}>
              Document Q&amp;A is retrieval-based by default: answers are composed from passages
              retrieved directly from the document index without an additional LLM call at query
              time, unless the administrator has enabled a generative answer mode.
            </p>
            <p style={{ marginTop: '0.75rem' }}>
              If your organisation operates under data-residency or confidentiality requirements,
              ensure the configured LLM provider meets those requirements before uploading
              sensitive material.
            </p>
          </Section>

          <Section id="storage" title="4. Data storage and retention">
            <p>
              All data is stored on infrastructure controlled by your organisation. {APP_NAME}{' '}
              does not operate a multi-tenant cloud service; your data stays on your servers.
              Retention periods are governed by your organisation's data-management policy. Admins
              can delete documents and user accounts through the platform.
            </p>
          </Section>

          <Section id="access" title="5. Access controls">
            <p>
              Access to data within {APP_NAME} is governed by role-based permissions. Only
              administrators can create or modify user accounts. Category-level permissions
              further restrict which documents each role can see. Passwords are never stored in
              plaintext; session tokens are issued as short-lived HttpOnly cookies.
            </p>
          </Section>

          <Section id="contact" title="6. Contact">
            <p>
              To request access to, correction of, or deletion of your data, contact:{' '}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.{' '}
              <em style={{ color: 'var(--muted)' }}>(TODO: replace with your organisation's real privacy contact.)</em>
            </p>
          </Section>
        </div>
      </div>
    </div>
  );
}
