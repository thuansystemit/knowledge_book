import { create } from 'zustand';

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'analyst' | 'viewer';
  is_active: boolean;
  created_at?: string;
}

interface AuthState {
  accessToken: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  setAccessToken: (token: string) => void;
  clear: () => void;
}

// Access token lives in memory only (never localStorage) — survives neither XSS
// nor tab reopen. The HttpOnly refresh cookie restores the session on reload.
export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAuth: (accessToken, user) => set({ accessToken, user }),
  setAccessToken: (accessToken) => set({ accessToken }),
  clear: () => set({ accessToken: null, user: null }),
}));
