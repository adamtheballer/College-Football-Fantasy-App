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
  apiPost,
  clearAccessTokenSession,
  getStoredAccessToken,
  storeAccessTokenSession,
} from "@/lib/api";

export interface User {
  firstName: string;
  email: string;
  id: number;
  isAdmin: boolean;
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
  email_verified_at?: string | null;
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
  login: (email: string, password: string) => Promise<User>;
  signup: (firstName: string, email: string, password: string) => Promise<User>;
  logout: () => void;
  requestPasswordReset: (email: string) => Promise<void>;
  confirmPasswordReset: (token: string, newPassword: string) => Promise<void>;
  listSessions: () => Promise<AuthSession[]>;
  revokeSession: (sessionId: number) => Promise<void>;
  logoutAll: () => Promise<void>;
  isLoggedIn: boolean;
  isBootstrapping: boolean;
};

const AUTH_CHANGED_EVENT = "cfb-auth-changed";
const USER_STORAGE_KEY = "cfb_user";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

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
    return { ...parsedUser, isAdmin: !!parsedUser.isAdmin };
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

    if (!storedUser && !storedToken) {
      setIsBootstrapping(false);
      return;
    }

    let cancelled = false;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 5000);

    apiGet<UserReadPayload>("/auth/me", undefined, controller.signal)
      .then((payload) => {
        if (cancelled) return;
        const nextUser = mapUserPayload(payload);
        safeStorageSet(USER_STORAGE_KEY, JSON.stringify(nextUser));
        setUser(nextUser);
      })
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
    const syncAuth = () => setUser(loadStoredUser());
    window.addEventListener("storage", syncAuth);
    window.addEventListener(AUTH_CHANGED_EVENT, syncAuth);
    return () => {
      window.removeEventListener("storage", syncAuth);
      window.removeEventListener(AUTH_CHANGED_EVENT, syncAuth);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const payload = await apiPost<AuthPayload>("/auth/login", { email, password });
    const nextUser = mapAuthPayload(payload);
    persistUser(nextUser, payload.access_token, payload.access_token_expires_at);
    queryClient.clear();
    setUser(nextUser);
    dispatchAuthChanged();
    return nextUser;
  }, [queryClient]);

  const signup = useCallback(async (firstName: string, email: string, password: string) => {
    const payload = await apiPost<AuthPayload>("/auth/signup", {
      first_name: firstName,
      email,
      password,
    });
    const nextUser = mapAuthPayload(payload);
    persistUser(nextUser, payload.access_token, payload.access_token_expires_at);
    queryClient.clear();
    setUser(nextUser);
    dispatchAuthChanged();
    return nextUser;
  }, [queryClient]);

  const logout = useCallback(() => {
    void apiPost("/auth/logout", {}).catch(() => {
      // Ignore network failures; local logout must still complete.
    });
    clearStoredAuth();
    queryClient.clear();
    setUser(null);
    dispatchAuthChanged();
  }, [queryClient]);

  const requestPasswordReset = useCallback(async (email: string) => {
    await apiPost("/auth/password-reset/request", { email });
  }, []);

  const confirmPasswordReset = useCallback(async (token: string, newPassword: string) => {
    await apiPost("/auth/password-reset/confirm", { token, new_password: newPassword });
    clearStoredAuth();
    queryClient.clear();
    setUser(null);
    dispatchAuthChanged();
  }, [queryClient]);

  const listSessions = useCallback(async () => {
    const payload = await apiGet<SessionsPayload>("/auth/sessions");
    return payload.sessions.map(mapSessionPayload);
  }, []);

  const revokeSession = useCallback(async (sessionId: number) => {
    await apiDelete(`/auth/sessions/${sessionId}`);
  }, []);

  const logoutAll = useCallback(async () => {
    await apiPost("/auth/logout-all", {});
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
      logout,
      requestPasswordReset,
      confirmPasswordReset,
      listSessions,
      revokeSession,
      logoutAll,
      isLoggedIn: !!user,
      isBootstrapping,
    }),
    [
      confirmPasswordReset,
      isBootstrapping,
      listSessions,
      login,
      logout,
      logoutAll,
      requestPasswordReset,
      revokeSession,
      signup,
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
