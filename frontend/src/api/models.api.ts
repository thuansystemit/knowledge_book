import { api } from './client';

export interface ModelOption {
  model_id: string;
  provider: string;
  label: string;
  is_local: boolean;
  credit_cost_extraction: number;
  credit_cost_chat: number;
}
export interface ModelsResponse {
  models: ModelOption[];
  default_extraction_model: string;
  default_chat_model: string;
  require_byo_key: boolean;
  /** 'retrieval' (no query-time LLM) or 'llm'. Controls whether chat shows a model picker. */
  chat_mode?: string;
  /** PAY-06: true when upgrading would unlock AI chat for this user. */
  chat_upgrade_available?: boolean;
}

export async function getModels(): Promise<ModelsResponse> {
  const { data } = await api.get<ModelsResponse>('/api/models');
  return data;
}
