import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { refresh } from './api/auth.api';
import { useAuthStore } from './store/authStore';
import { AppLayout } from './components/AppLayout';
import { PageSpinner } from './components/PageSpinner';
import { ProtectedRoute } from './components/ProtectedRoute';
import { PublicLayout } from './components/PublicLayout';
import { LoginPage } from './routes/LoginPage';
import { DocumentsPage } from './routes/DocumentsPage';
import { UploadPage } from './routes/UploadPage';
import { DocumentDetailPage } from './routes/DocumentDetailPage';
import { ProfilePage } from './routes/ProfilePage';
import { BillingPage } from './routes/BillingPage';
import { BillingSuccessPage, BillingCancelPage } from './routes/BillingResultPage';
import { UsersPage } from './routes/admin/UsersPage';
import { CategoriesPage } from './routes/admin/CategoriesPage';
import { ConfigPage } from './routes/admin/ConfigPage';
import { AboutPage } from './routes/legal/About';
import { PrivacyPage } from './routes/legal/Privacy';
import { TermsPage } from './routes/legal/Terms';

export default function App() {
  const setAuth = useAuthStore((s) => s.setAuth);
  const [ready, setReady] = useState(false);

  // On load, try a silent refresh: the HttpOnly cookie restores the session
  // without the user re-entering credentials.
  useEffect(() => {
    refresh()
      .then((d) => setAuth(d.access_token, d.user))
      .catch(() => { /* not logged in */ })
      .finally(() => setReady(true));
  }, [setAuth]);

  if (!ready) return <PageSpinner />;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/billing" element={<BillingPage />} />
          <Route path="/billing/success" element={<BillingSuccessPage />} />
          <Route path="/billing/cancel" element={<BillingCancelPage />} />
          {/* Upload is restricted to roles that can upload (viewers can't). */}
          <Route element={<ProtectedRoute roles={['admin', 'analyst']} />}>
            <Route path="/documents/new" element={<UploadPage />} />
          </Route>
        </Route>
      </Route>

      {/*
       * Legal pages are intentionally PUBLIC — no authentication required.
       * They are reachable from the AppFooter on the login page as well as
       * from within the authenticated app. PublicLayout renders a minimal
       * branded chrome (wordmark + footer) without any user-specific nav.
       */}
      <Route element={<PublicLayout />}>
        <Route path="/about"   element={<AboutPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms"   element={<TermsPage />} />
      </Route>

      <Route element={<ProtectedRoute roles={['admin']} />}>
        <Route element={<AppLayout />}>
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/categories" element={<CategoriesPage />} />
          <Route path="/admin/config" element={<ConfigPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/documents" replace />} />
    </Routes>
  );
}
