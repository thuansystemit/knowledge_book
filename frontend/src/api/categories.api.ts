import { api } from './client';

export interface Category {
  id: string; name: string; description: string | null;
  my_grant: string | null; doc_count: number;
}
export interface CatPermission { id: string; user_id: string; grant_type: string; }

export async function listCategories(): Promise<Category[]> {
  return (await api.get('/api/categories')).data;
}
export async function createCategory(name: string, description?: string): Promise<Category> {
  return (await api.post('/api/categories', { name, description })).data;
}
export async function deleteCategory(id: string): Promise<void> {
  await api.delete(`/api/categories/${id}`);
}
export async function listPermissions(id: string): Promise<CatPermission[]> {
  return (await api.get(`/api/categories/${id}/permissions`)).data;
}
export async function addPermission(id: string, user_id: string, grant_type: string): Promise<void> {
  await api.post(`/api/categories/${id}/permissions`, { user_id, grant_type });
}
export async function revokePermission(id: string, permId: string): Promise<void> {
  await api.delete(`/api/categories/${id}/permissions/${permId}`);
}
