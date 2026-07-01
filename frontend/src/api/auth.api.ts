import { api } from './client';
import type { User } from '../store/authStore';

export async function login(email: string, password: string) {
  const { data } = await api.post<{ access_token: string; user: User }>('/auth/login', {
    email,
    password,
  });
  return data;
}

export async function refresh() {
  const { data } = await api.post<{ access_token: string; user: User }>('/auth/refresh', {});
  return data;
}

export async function logout() {
  await api.post('/auth/logout', {});
}

// Admin user management
export interface AdminUser extends User {
  created_at: string;
}
export async function listUsers() {
  const { data } = await api.get<AdminUser[]>('/admin/users');
  return data;
}
export async function createUser(body: {
  email: string;
  password: string;
  name: string;
  role: string;
}) {
  const { data } = await api.post<AdminUser>('/admin/users', body);
  return data;
}
export async function updateUser(
  id: string,
  body: { role?: string; is_active?: boolean; password?: string },
) {
  const { data } = await api.patch<AdminUser>(`/admin/users/${id}`, body);
  return data;
}
