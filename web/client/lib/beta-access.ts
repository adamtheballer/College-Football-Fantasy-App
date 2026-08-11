import { apiPost } from "@/lib/api";

const RESERVATION_STORAGE_KEY = "cfb_beta_access_reservation";

export const BETA_ACCESS_CODE_PREFIX = "EARLY-";

// Legacy variable name: controls only the optional Early Access Pro-code offer.
// It must never determine whether a visitor can create or use an account.
export const betaAccessEnabled = import.meta.env.VITE_BETA_ACCESS_ENABLED === "true";

type BetaAccessValidationPayload = {
  reservation_token: string;
  reservation_expires_at: string;
  email: string;
  existing_account?: boolean;
};

export type BetaAccessReservation = {
  token: string;
  expiresAt: string;
  email: string;
  existingAccount: boolean;
};

const safeSessionGet = (key: string): string | null => {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
};

const safeSessionSet = (key: string, value: string) => {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    // A private-browser storage failure simply prevents this optional benefit
    // from being claimed in the current session; normal signup still works.
  }
};

const safeSessionRemove = (key: string) => {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // Ignore storage cleanup failures.
  }
};

export const getBetaAccessReservation = (): BetaAccessReservation | null => {
  const stored = safeSessionGet(RESERVATION_STORAGE_KEY);
  if (!stored) return null;
  try {
    const value = JSON.parse(stored) as BetaAccessReservation;
    if (!value.token || !value.email || Number.isNaN(Date.parse(value.expiresAt)) || Date.parse(value.expiresAt) <= Date.now()) {
      safeSessionRemove(RESERVATION_STORAGE_KEY);
      return null;
    }
    return value;
  } catch {
    safeSessionRemove(RESERVATION_STORAGE_KEY);
    return null;
  }
};

export const clearBetaAccessReservation = () => safeSessionRemove(RESERVATION_STORAGE_KEY);

/**
 * The beta form displays the shared prefix as fixed UI chrome. Accepting a
 * pasted full code as well keeps the field forgiving without ever sending a
 * partial value to the API.
 */
export const normalizeBetaAccessCodeSuffix = (value: string): string =>
  value
    .trim()
    .toUpperCase()
    .replace(/^EARLY-?/, "")
    .replace(/[^A-Z0-9]/g, "")
    .slice(0, 6);

export const betaAccessCodeFromSuffix = (suffix: string): string =>
  `${BETA_ACCESS_CODE_PREFIX}${normalizeBetaAccessCodeSuffix(suffix)}`;

export const validateBetaAccess = async (email: string, code: string): Promise<BetaAccessReservation> => {
  const payload = await apiPost<BetaAccessValidationPayload>("/beta-access/validate", { email, code });
  const reservation: BetaAccessReservation = {
    token: payload.reservation_token,
    expiresAt: payload.reservation_expires_at,
    email: payload.email,
    existingAccount: !!payload.existing_account,
  };
  if (!reservation.token || !reservation.email || Number.isNaN(Date.parse(reservation.expiresAt))) {
    throw new Error("Unable to verify your Early Access Pro code. Please try again.");
  }
  safeSessionSet(RESERVATION_STORAGE_KEY, JSON.stringify(reservation));
  return reservation;
};
