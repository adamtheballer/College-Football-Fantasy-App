import { apiGet, apiPost } from "./api";
export type Membership = {
  plan: "free" | "pro";
  active: boolean;
  launch_at: string | null;
  enforcement_active: boolean;
  amount_cents: number;
  currency: string;
  interval: string;
  expires_at: string | null;
  source: string | null;
  cancel_at_period_end: boolean;
  league_limit: number | null;
  league_count: number;
  features: {
    unlimited_leagues: boolean;
    dynasty: boolean;
    player_pictures: boolean;
    weekly_challenges: boolean;
    live_refresh_seconds: number;
  };
  web_checkout_ready: boolean;
  apple_purchase_ready: boolean;
  apple_product_id: string | null;
  apple_account_token: string | null;
  has_stripe_customer: boolean;
  free_leagues: { id: number; name: string; selected: boolean }[];
  free_league_choice_locked: boolean;
};
export const membershipApi = {
  status: () => apiGet<Membership>("/membership"),
  checkout: () => apiPost<{ url: string }>("/membership/checkout", {}),
  portal: () => apiPost<{ url: string }>("/membership/portal", {}),
  sync: () => apiPost<Membership>("/membership/sync", {}),
  chooseFreeLeagues: (league_ids: number[]) =>
    apiPost<Membership>("/membership/free-leagues", { league_ids }),
  verifyApple: (signed_transaction: string) =>
    apiPost<Membership>("/membership/apple/verify", { signed_transaction }),
};
