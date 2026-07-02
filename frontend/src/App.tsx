import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { refresh } from './api/auth.api';
import { useAuthStore } from './store/authStore';
import { AppLayout } from './components/AppLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './routes/LoginPage';
import { DocumentsPage } from './routes/DocumentsPage';
import { UploadPage } from './routes/UploadPage';
import { DocumentDetailPage } from './routes/DocumentDetailPage';
import { UsersPage } from './routes/admin/UsersPage';
import { CategoriesPage } from './routes/admin/CategoriesPage';

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

  if (!ready) return (
    <div className="d-flex align-items-center justify-content-center min-vh-100 text-secondary">
      <div className="spinner-border text-primary me-2" role="status" style={{ width: 22, height: 22 }} /> Loading…
    </div>
  );

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/new" element={<UploadPage />} />
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute roles={['admin']} />}>
        <Route element={<AppLayout />}>
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/categories" element={<CategoriesPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/documents" replace />} />
    </Routes>
  );
}
