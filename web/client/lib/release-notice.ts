import { apiReleaseNoticeClaim } from "@/lib/api";

export const UPDATE_RELEASE = "1.03";
export type ReleaseNoticeClaim = {
  account_id: number;
  release_key: "1.03";
  authorization: "granted" | "already_seen";
  claimed_at: string;
};

const seen = new Set<number>();
const claims = new Map<number, Promise<ReleaseNoticeClaim>>();
const storageKey = (accountId: number) =>
  `cffb_update_${UPDATE_RELEASE}_seen_${accountId}`;

export function updateNoticeSeen(accountId: number): boolean {
  if (seen.has(accountId)) return true;
  try {
    return localStorage.getItem(storageKey(accountId)) === "true";
  } catch {
    return false;
  }
}

export function rememberUpdateNotice(accountId: number): void {
  seen.add(accountId);
  claims.delete(accountId);
  try {
    localStorage.setItem(storageKey(accountId), "true");
  } catch {
    /* The account receipt and memory still enforce once-only display. */
  }
}

/** Coalesce StrictMode/remounts without aborting or duplicating a durable claim.
 * Keep an unpresented grant in memory if navigation briefly makes a screen unsafe.
 */
export function requestUpdateNotice(
  accountId: number,
): Promise<ReleaseNoticeClaim> {
  const pending = claims.get(accountId);
  if (pending) return pending;
  const claim = apiReleaseNoticeClaim<ReleaseNoticeClaim>(accountId).catch(
    (error) => {
      claims.delete(accountId);
      throw error;
    },
  );
  claims.set(accountId, claim);
  return claim;
}
