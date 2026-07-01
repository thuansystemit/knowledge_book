import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

/** Gate routes behind authentication and (optionally) a set of roles. */
export function ProtectedRoute({ roles }: { roles?: string[] }) {
  const { accessToken, user } = useAuthStore();
  if (!accessToken || !user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/documents" replace />;
  return <Outlet />;
}
