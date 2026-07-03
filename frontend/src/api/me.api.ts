import { api } from './client';

export async function setMyModelDefaults(body: {
  default_extraction_model?: string | null;
  default_chat_model?: string | null;
}): Promise<void> {
  await api.put('/api/me/model-defaults', body);
}
