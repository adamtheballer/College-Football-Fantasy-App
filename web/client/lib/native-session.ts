import { SecureStoragePlugin } from "capacitor-secure-storage-plugin";

const REFRESH_TOKEN_KEY = "cffb_native_refresh_token";

export const isNativeSessionRuntime = (): boolean =>
  typeof window !== "undefined" && window.location.protocol === "capacitor:";

export const nativeSessionHeaders = (): Record<string, string> =>
  isNativeSessionRuntime() ? { "X-CFFB-Native-Session": "ios" } : {};

export const readNativeRefreshToken = async (): Promise<string | null> => {
  if (!isNativeSessionRuntime()) return null;
  try {
    const result = await SecureStoragePlugin.get({ key: REFRESH_TOKEN_KEY });
    return result.value || null;
  } catch (error) {
    // The plugin rejects for a missing key. Other Keychain failures must not
    // be mistaken for a revoked session and must not erase the cached user.
    if (error instanceof Error && error.message.includes("does not exist")) return null;
    throw error;
  }
};

export const saveNativeRefreshToken = async (token: string | null | undefined): Promise<void> => {
  if (!isNativeSessionRuntime()) return;
  if (!token) throw new Error("The server did not provide a native refresh session.");
  const result = await SecureStoragePlugin.set({ key: REFRESH_TOKEN_KEY, value: token });
  if (!result.value) throw new Error("Could not securely save this device's sign-in session.");
};

export const clearNativeRefreshToken = async (): Promise<void> => {
  if (!isNativeSessionRuntime()) return;
  const token = await readNativeRefreshToken();
  if (token) await SecureStoragePlugin.remove({ key: REFRESH_TOKEN_KEY });
};
