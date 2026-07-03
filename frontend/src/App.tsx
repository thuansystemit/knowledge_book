import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { refresh } from './api/auth.api';
import { useAuthStore } from './store/authStore';
import { AppLayout } from './components/AppLayout';
import { PageSpinner } from './components/PageSpinner';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './routes/LoginPage';
import { DocumentsPage } from './routes/DocumentsPage';
import { UploadPage } from './routes/UploadPage';
import { DocumentDetailPage } from './routes/DocumentDetailPage';
import { ProfilePage } from './routes/ProfilePage';
import { UsersPage } from './routes/admin/UsersPage';
import { CategoriesPage } from './routes/admin/CategoriesPage';
import { ConfigPage } from './routes/admin/ConfigPage';

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
          {/* Upload is restricted to roles that can upload (viewers can't). */}
          <Route element={<ProtectedRoute roles={['admin', 'analyst']} />}>
            <Route path="/documents/new" element={<UploadPage />} />
          </Route>
        </Route>
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
