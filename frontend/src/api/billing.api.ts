import { api } from './client';

export type Plan = 'free' | 'pro' | 'scholar';
export type Interval = 'monthly' | 'annual';

export interface Usage {
  plan: Plan;
  limit: number | null;   // null = unlimited
  used: number;
  remaining: number | null;
  credits: number;        // non-expiring extra docs (PAY-05)
  resets_at: string;      // ISO
}

export interface BillingConfig {
  enabled: boolean;                       // Stripe configured server-side
  available: Record<string, boolean>;     // e.g. { pro_monthly: true, ... }
  credit_packs: Record<string, boolean>;  // e.g. { "5": true, "10": true }
  current_plan: Plan;
  plan_status: 'none' | 'active' | 'past_due' | 'canceled';
}

/** Current user's monthly upload quota + usage (PAY-06 meter). */
export async function getUsage(): Promise<Usage> {
  const { data } = await api.get<Usage>('/api/usage');
  return data;
}

/** Whether billing is live and which (plan, interval) prices exist. */
export async function getBillingConfig(): Promise<BillingConfig> {
  const { data } = await api.get<BillingConfig>('/billing/config');
  return data;
}

/** Start a Stripe-hosted checkout; returns the URL to redirect the browser to. */
export async function createCheckout(plan: Exclude<Plan, 'free'>, interval: Interval): Promise<string> {
  const { data } = await api.post<{ url: string }>('/billing/checkout', { plan, interval });
  return data.url;
}

/** Buy a one-time credit pack ("5" | "10"); returns the Stripe checkout URL. */
export async function buyCredits(pack: '5' | '10'): Promise<string> {
  const { data } = await api.post<{ url: string }>('/billing/credits', { pack });
  return data.url;
}

/** Open the Stripe billing portal (manage/cancel); returns the URL. */
export async function openPortal(): Promise<string> {
  const { data } = await api.post<{ url: string }>('/billing/portal', {});
  return data.url;
}
