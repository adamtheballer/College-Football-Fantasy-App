import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  clearAccessTokenSession,
  getStoredAccessToken,
  isStoredAccessTokenExpired,
  restoreAccessTokenSession,
  storeAccessTokenSession,
} from "@/lib/api";
import { clearBrowserPushIdentity, syncBrowserPushIdentity } from "@/lib/push-notifications";

export interface User {
  firstName: string;
  email: string;
  id: number;
  isAdmin: boolean;
  avatarUrl: string | null;
  managerNameChangeAvailableAt?: string | null;
}

export type AuthSession = {
  id: number;
  issuedAt: string;
  expiresAt: string;
  lastUsedAt: string | null;
  userAgent: string | null;
  ipAddress: string | null;
  isCurrent: boolean;
};

type AuthUserPayload = {
  id: number;
  first_name: string;
  email: string;
  is_admin?: boolean;
  avatar_url?: string | null;
  email_verified_at?: string | null;
  manager_name_change_available_at?: string | null;
};

type AuthPayload = {
  access_token: string;
  access_token_expires_at: string;
  user: AuthUserPayload;
};

type UserReadPayload = AuthUserPayload;

type AuthSessionPayload = {
  id: number;
  issued_at: string;
  expires_at: string;
  last_used_at?: string | null;
  user_agent?: string | null;
  ip_address?: string | null;
  is_current?: boolean;
};

type SessionsPayload = {
  sessions: AuthSessionPayload[];
};

type AuthContextValue = {
  user: User | null;
  login: (email: string, password: string, betaAccessReservation?: string) => Promise<User>;
  signup: (firstName: string, email: string, password: string, betaAccessReservation?: string) => Promise<User>;
  updateProfile: (input: UpdateProfileInput) => Promise<User>;
  logout: () => void;
  resetPasswordWithCurrentPassword: (
    email: string,
    currentPassword: string,
    newPassword: string,
    confirmNewPassword: string,
  ) => Promise<void>;
  requestPasswordReset: (email: string) => Promise<void>;
  requestPasswordResetForCurrentUser: () => Promise<void>;
  validatePasswordReset: (token: string) => Promise<boolean>;
  confirmPasswordReset: (token: string, newPassword: string, confirmPassword: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string, confirmNewPassword: string) => Promise<void>;
  listSessions: () => Promise<AuthSession[]>;
  revokeSession: (sessionId: number) => Promise<void>;
  logoutAll: () => Promise<void>;
  isLoggedIn: boolean;
  isBootstrapping: boolean;
};

const AUTH_CHANGED_EVENT = "cfb-auth-changed";
const USER_STORAGE_KEY = "cfb_user";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export type UpdateProfileInput = {
  firstName?: string;
  avatarUrl?: string | null;
};

const safeStorageGet = (key: string): string | null => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

const safeStorageSet = (key: string, value: string) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Ignore storage errors to keep app usable.
  }
};

const safeStorageRemove = (key: string) => {
  try {
    localStorage.removeItem(key);
  } catch {
    // Ignore storage errors to keep app usable.
  }
};

const dispatchAuthChanged = () => {
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
};

const clearStoredAuth = () => {
  safeStorageRemove(USER_STORAGE_KEY);
  clearAccessTokenSession();
};

const loadStoredUser = (): User | null => {
  const savedUser = safeStorageGet(USER_STORAGE_KEY);
  if (!savedUser) {
    return null;
  }

  try {
    const parsedUser = JSON.parse(savedUser) as User;
    if (!parsedUser?.id || !parsedUser?.email) {
      clearStoredAuth();
      return null;
    }
    return {
      ...parsedUser,
      isAdmin: !!parsedUser.isAdmin,
      avatarUrl: parsedUser.avatarUrl ?? null,
      managerNameChangeAvailableAt: parsedUser.managerNameChangeAvailableAt ?? null,
    };
  } catch {
    clearStoredAuth();
    return null;
  }
};

const persistUser = (user: User, accessToken: string, accessTokenExpiresAt: string) => {
  safeStorageSet(USER_STORAGE_KEY, JSON.stringify(user));
  storeAccessTokenSession(accessToken, accessTokenExpiresAt);
};

const mapUserPayload = (payload: AuthUserPayload): User => ({
  id: payload.id,
  firstName: payload.first_name,
  email: payload.email,
  isAdmin: !!payload.is_admin,
  avatarUrl: payload.avatar_url ?? null,
  managerNameChangeAvailableAt: payload.manager_name_change_available_at ?? null,
});

const mapAuthPayload = (payload: AuthPayload): User => mapUserPayload(payload.user);

const mapSessionPayload = (payload: AuthSessionPayload): AuthSession => ({
  id: payload.id,
  issuedAt: payload.issued_at,
  expiresAt: payload.expires_at,
  lastUsedAt: payload.last_used_at ?? null,
  userAgent: payload.user_agent ?? null,
  ipAddress: payload.ip_address ?? null,
  isCurrent: !!payload.is_current,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  useEffect(() => {
    const storedUser = loadStoredUser();
    const storedToken = getStoredAccessToken();
    setUser(storedUser);

    let cancelled = false;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 5000);

    const restoreSession = async () => {
      // The refresh token is intentionally HTTP-only, so it can survive an
      // iOS/webview access-token cleanup. Try it first whenever the short
      // access token is missing or expired; this restores a valid signed-in
      // user without sending them back through the login screen.
      if (!storedToken || isStoredAccessTokenExpired()) {
        const refreshResult = await restoreAccessTokenSession(controller.signal);
        if (cancelled) return;

        if (refreshResult === "terminal_failure") {
          clearStoredAuth();
          setUser(null);
          return;
        }

        // Keep a previously rendered user signed in during a temporary
        // outage; refresh will be retried by the next authenticated request.
        // Without a cached user there is nothing trustworthy to render.
        if (refreshResult === "transient_failure") {
          return;
        }
      }

      const payload = await apiGet<UserReadPayload>("/auth/me", undefined, controller.signal);
      if (!cancelled) {
        const nextUser = mapUserPayload(payload);
        safeStorageSet(USER_STORAGE_KEY, JSON.stringify(nextUser));
        setUser(nextUser);
      }
    };

    void restoreSession()
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearStoredAuth();
          setUser(null);
        }
      })
      .finally(() => {
        window.clearTimeout(timeoutId);
        if (!cancelled) {
          setIsBootstrapping(false);
        }
      });

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (user) {
      void syncBrowserPushIdentity(user.id);
    }
  }, [user?.id]);

  useEffect(() => {
    const syncAuth = () => setUser(loadStoredUser());
    window.addEventListener("storage", syncAuth);
    window.addEventListener(AUTH_CHANGED_EVENT, syncAuth);
    return () => {
      window.removeEventListener("storage", syncAuth);
      window.removeEventListener(AUTH_CHANGED_EVENT, syncAuth);
    };
  }, []);

  const login = useCallback(async (email: string, password: string, betaAccessReservation?: string) => {
    const payload = await apiPost<AuthPayload>("/auth/login", {
      email,
      password,
      beta_access_reservation: betaAccessReservation,
    });
    const nextUser = mapAuthPayload(payload);
    persistUser(nextUser, payload.access_token, payload.access_token_expires_at);
    queryClient.clear();
    setUser(nextUser);
    dispatchAuthChanged();
    return nextUser;
  }, [queryClient]);

  const signup = useCallback(async (firstName: string, email: string, password: string, betaAccessReservation?: string) => {
    const payload = await apiPost<AuthPayload>("/auth/signup", {
      first_name: firstName,
      email,
      password,
      beta_access_reservation: betaAccessReservation,
    });
    const nextUser = mapAuthPayload(payload);
    persistUser(nextUser, payload.access_token, payload.access_token_expires_at);
    queryClient.clear();
    setUser(nextUser);
    dispatchAuthChanged();
    return nextUser;
  }, [queryClient]);

  const updateProfile = useCallback(async (input: UpdateProfileInput) => {
    const request: Record<string, string | null> = {};
    if (input.firstName !== undefined) request.first_name = input.firstName;
    if (input.avatarUrl !== undefined) request.avatar_url = input.avatarUrl;
    const payload = await apiPatch<AuthUserPayload>("/auth/me", request);
    const nextUser = mapUserPayload(payload);
    safeStorageSet(USER_STORAGE_KEY, JSON.stringify(nextUser));
    setUser(nextUser);
    dispatchAuthChanged();
    // Manager identity appears in cached league, draft, matchup, and chat
    // responses. Mark every related view stale so the newly saved photo is
    // fetched immediately instead of waiting for its normal refresh window.
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["leagues"] }),
      queryClient.invalidateQueries({ queryKey: ["league"] }),
      queryClient.invalidateQueries({ queryKey: ["draft-room"] }),
      queryClient.invalidateQueries({ queryKey: ["team"] }),
      queryClient.invalidateQueries({ queryKey: ["chat"] }),
    ]);
    return nextUser;
  }, [queryClient]);

  const logout = useCallback(() => {
    void apiPost("/auth/logout", {}).catch(() => {
      // Ignore network failures; local logout must still complete.
    });
    clearBrowserPushIdentity();
    clearStoredAuth();
    queryClient.clear();
    setUser(null);
    dispatchAuthChanged();
  }, [queryClient]);

  const clearPasswordChangeAuth = useCallback(() => {
    clearBrowserPushIdentity();
    clearStoredAuth();
    queryClient.clear();
    setUser(null);
    dispatchAuthChanged();
  }, [queryClient]);

  const resetPasswordWithCurrentPassword = useCallback(async (
    email: string,
    currentPassword: string,
    newPassword: string,
    confirmNewPassword: string,
  ) => {
    await apiPost("/auth/reset-password-with-current-password", {
      email,
      current_password: currentPassword,
      new_password: newPassword,
      confirm_new_password: confirmNewPassword,
    });
    clearPasswordChangeAuth();
  }, [clearPasswordChangeAuth]);

  const requestPasswordReset = useCallback(async (email: string) => {
    await apiPost("/auth/password-reset/request", { email });
  }, []);

  const requestPasswordResetForCurrentUser = useCallback(async () => {
    await apiPost("/auth/password-reset/request-for-current-user", {});
  }, []);

  const validatePasswordReset = useCallback(async (token: string) => {
    const response = await apiPost<{ valid: boolean }>("/auth/password-reset/validate", { token });
    return response.valid === true;
  }, []);

  const confirmPasswordReset = useCallback(async (token: string, newPassword: string, confirmPassword: string) => {
    await apiPost("/auth/password-reset/confirm", {
      token,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    clearPasswordChangeAuth();
  }, [clearPasswordChangeAuth]);

  const changePassword = useCallback(async (
    currentPassword: string,
    newPassword: string,
    confirmNewPassword: string,
  ) => {
    await apiPost("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
      confirm_new_password: confirmNewPassword,
    });
    clearPasswordChangeAuth();
  }, [clearPasswordChangeAuth]);

  const listSessions = useCallback(async () => {
    const payload = await apiGet<SessionsPayload>("/auth/sessions");
    return payload.sessions.map(mapSessionPayload);
  }, []);

  const revokeSession = useCallback(async (sessionId: number) => {
    await apiDelete(`/auth/sessions/${sessionId}`);
  }, []);

  const logoutAll = useCallback(async () => {
    await apiPost("/auth/logout-all", {});
    clearBrowserPushIdentity();
    clearStoredAuth();
    queryClient.clear();
    setUser(null);
    dispatchAuthChanged();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      login,
      signup,
      updateProfile,
      logout,
      resetPasswordWithCurrentPassword,
      requestPasswordReset,
      requestPasswordResetForCurrentUser,
      validatePasswordReset,
      confirmPasswordReset,
      changePassword,
      listSessions,
      revokeSession,
      logoutAll,
      isLoggedIn: !!user,
      isBootstrapping,
    }),
    [
      changePassword,
      confirmPasswordReset,
      isBootstrapping,
      listSessions,
      login,
      logout,
      logoutAll,
      resetPasswordWithCurrentPassword,
      requestPasswordReset,
      requestPasswordResetForCurrentUser,
      revokeSession,
      signup,
      updateProfile,
      validatePasswordReset,
      user,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
