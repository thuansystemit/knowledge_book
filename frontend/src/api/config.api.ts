import { api } from './client';
import type { ModelOption } from './models.api';

export interface UserModelRow {
  id: string; email: string; name: string; role: string;
  default_extraction_model: string | null;
  default_chat_model: string | null;
}
export interface OrgPolicy {
  allowed_models: string[];
  default_extraction_model: string | null;
  default_chat_model: string | null;
  require_byo_key: boolean;
}
export interface ModelAssignments {
  org_id: string;
  system_default: string;
  models: ModelOption[];
  policy: OrgPolicy;
  users: UserModelRow[];
}

export async function getModelAssignments(): Promise<ModelAssignments> {
  return (await api.get('/api/admin/model-assignments')).data;
}

export async function setUserModelDefaults(
  userId: string,
  body: { default_extraction_model?: string; default_chat_model?: string },
): Promise<void> {
  await api.put(`/api/admin/users/${userId}/model-defaults`, body);
}

export async function setOrgModelPolicy(
  orgId: string,
  body: Partial<OrgPolicy>,
): Promise<void> {
  await api.put(`/api/orgs/${orgId}/model-policy`, body);
}
