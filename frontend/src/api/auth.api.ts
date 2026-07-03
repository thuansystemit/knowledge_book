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

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  return data;
}
