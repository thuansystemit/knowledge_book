import { APP_NAME } from '../../lib/constants';

/* ─────────────────────────────────────────────────────────────────────────
   TEMPLATE NOTICE
   This is a placeholder Terms & Conditions document. It has not been
   reviewed by legal counsel and must not be treated as legal advice or a
   binding commitment. Replace with terms reviewed by qualified legal
   professionals before any production deployment.
   ───────────────────────────────────────────────────────────────────────── */

const LEGAL_EMAIL = 'legal@example.com'; // TODO: replace with real address

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

export function TermsPage() {
  return (
    <div style={{ maxWidth: 720 }}>
      <h1 className="page-title">Terms &amp; Conditions</h1>
      <p className="page-subtitle" style={{ marginBottom: '0.75rem' }}>
        Last updated: 1 July 2026
      </p>

      <div className="alert alert-secondary mb-4" role="note">
        <strong>Template notice:</strong> This is a placeholder Terms &amp; Conditions document
        provided for informational purposes only. It has not been reviewed by legal counsel and
        should not be treated as legal advice or a binding commitment. Replace this content with
        terms reviewed by qualified legal professionals before deployment. Details marked with{' '}
        <em>TODO</em> must be filled in before this document is published.
      </div>

      <div className="card">
        <div className="card-body" style={{ padding: '1.5rem 1.75rem' }}>
          <p style={{ fontSize: '0.875rem', lineHeight: 1.7, color: 'var(--body)', marginBottom: '1.75rem' }}>
            Please read these Terms &amp; Conditions carefully before using {APP_NAME}. By
            accessing or using the platform, you agree to be bound by these terms. If you do not
            agree, do not use the platform.
          </p>

          <Section id="acceptance" title="1. Acceptance of terms">
            <p>
              By creating an account or using any feature of {APP_NAME}, you confirm that you
              have read, understood, and agree to these Terms &amp; Conditions. Your use of the
              platform constitutes ongoing acceptance of the terms in force at the time of use.
            </p>
          </Section>

          <Section id="service" title="2. Description of service">
            <p>
              {APP_NAME} is an internal document-intelligence platform that processes uploaded
              PDF documents to produce summaries, concept graphs, chapter guides, and a
              retrieval-based Q&amp;A interface. The platform is made available to authorised
              users within your organisation only.
            </p>
          </Section>

          <Section id="acceptable-use" title="3. Acceptable use">
            <p>You agree not to:</p>
            <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              <li>Upload documents you do not have the right to process or share.</li>
              <li>Attempt to circumvent access controls, authentication, or permissions.</li>
              <li>Use the platform for any unlawful purpose or in violation of applicable law.</li>
              <li>
                Reverse-engineer, decompile, or otherwise attempt to extract the source code of
                the platform without written authorisation.
              </li>
              <li>
                Upload malicious files, or attempt to interfere with the platform's availability
                or integrity.
              </li>
            </ul>
          </Section>

          <Section id="accounts" title="4. User accounts and responsibilities">
            <p>
              Accounts are created by administrators. You are responsible for maintaining the
              confidentiality of your credentials and for all activity that occurs under your
              account. Notify your administrator immediately if you suspect unauthorised access.
            </p>
            <p style={{ marginTop: '0.75rem' }}>
              Your role (Admin, Editor, or Viewer) determines what actions you may perform within
              the platform. You must not attempt to perform actions beyond your assigned role.
            </p>
          </Section>

          <Section id="ip" title="5. Intellectual property">
            <p>
              You retain ownership of any documents you upload. By uploading a document you grant
              the platform a limited licence to process the content solely for the purpose of
              providing you with the platform's features (extraction, summarisation, indexing).
            </p>
            <p style={{ marginTop: '0.75rem' }}>
              The platform's software, design, and generated outputs (summaries, concept labels,
              chapter guides) are the property of the organisation operating this deployment.
              {' '}<em style={{ color: 'var(--muted)' }}>(TODO: clarify ownership with legal.)</em>
            </p>
          </Section>

          <Section id="disclaimers" title="6. Disclaimers and limitation of liability">
            <p>
              The platform is provided "as is" and "as available" without warranty of any kind,
              express or implied. We do not warrant that the platform will be error-free,
              uninterrupted, or that extracted summaries and concept graphs will be accurate or
              complete — all AI-generated outputs should be verified against source material.
            </p>
            <p style={{ marginTop: '0.75rem' }}>
              To the maximum extent permitted by applicable law, we shall not be liable for any
              indirect, incidental, special, consequential, or punitive damages arising out of
              your use of or inability to use the platform.
              {' '}<em style={{ color: 'var(--muted)' }}>(TODO: review liability caps with legal.)</em>
            </p>
          </Section>

          <Section id="termination" title="7. Termination">
            <p>
              Administrators may suspend or delete any account at any time. Your access to the
              platform terminates when your account is removed or your organisation discontinues
              use of the platform. On termination, your uploaded documents remain on the
              organisation's infrastructure under their data-retention policy.
            </p>
          </Section>

          <Section id="changes" title="8. Changes to these terms">
            <p>
              We may update these Terms &amp; Conditions from time to time. When we do, we will
              update the "Last updated" date above. Continued use of the platform after changes
              are posted constitutes acceptance of the revised terms.
            </p>
          </Section>

          <Section id="contact" title="9. Contact">
            <p>
              Questions about these terms should be directed to:{' '}
              <a href={`mailto:${LEGAL_EMAIL}`}>{LEGAL_EMAIL}</a>.{' '}
              <em style={{ color: 'var(--muted)' }}>(TODO: replace with your organisation's real legal contact.)</em>
            </p>
          </Section>
        </div>
      </div>
    </div>
  );
}
