import { api } from './client';
import type { User } from '../store/authStore';

// Re-exports the base User type extended with server-side admin fields.
export interface AdminUser extends User {
  created_at: string;
}

export async function listUsers(): Promise<AdminUser[]> {
  const { data } = await api.get<AdminUser[]>('/admin/users');
  return data;
}

export async function createUser(body: {
  email: string;
  password: string;
  name: string;
  role: string;
}): Promise<AdminUser> {
  const { data } = await api.post<AdminUser>('/admin/users', body);
  return data;
}

export async function updateUser(
  id: string,
  body: { role?: string; is_active?: boolean; password?: string },
): Promise<AdminUser> {
  const { data } = await api.patch<AdminUser>(`/admin/users/${id}`, body);
  return data;
}
