const SIGNED_IN_DEVICE_STORAGE_KEY = "cfb_known_sign_in_device";

const safeLocalGet = (key: string): string | null => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

const safeLocalSet = (key: string, value: string) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    // This is only a routing convenience. Storage failures must never affect
    // the actual authentication or beta-access decision.
  }
};

/**
 * This stores no identity, token, or entitlement. It only lets a browser that
 * has completed a real sign-in begin at the sign-in form after it logs out.
 */
export const rememberSignedInDevice = () => safeLocalSet(SIGNED_IN_DEVICE_STORAGE_KEY, "1");

export const hasSignedInOnDevice = () => safeLocalGet(SIGNED_IN_DEVICE_STORAGE_KEY) === "1";

export const getUnauthenticatedEntryPath = (
  isBetaAccessEnabled: boolean,
  isKnownSignInDevice: boolean,
) => (isBetaAccessEnabled && !isKnownSignInDevice ? "/login?flow=beta" : "/login");
