import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost, ApiError } from "@/lib/api";

export interface User {
  firstName: string;
  email: string;
  token: string;
  id: number;
}

type AuthPayload = {
  user: {
    id: number;
    first_name: string;
    email: string;
    api_token: string;
  };
};

type AuthContextValue = {
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  signup: (firstName: string, email: string, password: string) => Promise<User>;
  logout: () => void;
  isLoggedIn: boolean;
  isBootstrapping: boolean;
};

const AUTH_CHANGED_EVENT = "cfb-auth-changed";
const USER_STORAGE_KEY = "cfb_user";
const TOKEN_STORAGE_KEY = "cfb_token";

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
  safeStorageRemove(TOKEN_STORAGE_KEY);
};

const loadStoredUser = (): User | null => {
  const savedUser = safeStorageGet(USER_STORAGE_KEY);
  const savedToken = safeStorageGet(TOKEN_STORAGE_KEY);
  if (!savedUser || !savedToken) {
    clearStoredAuth();
    return null;
  }

  try {
    const parsedUser = JSON.parse(savedUser) as User;
    if (!parsedUser?.id || !parsedUser?.email) {
      clearStoredAuth();
      return null;
    }
    return { ...parsedUser, token: savedToken };
  } catch {
    clearStoredAuth();
    return null;
  }
};

const persistUser = (user: User) => {
  safeStorageSet(USER_STORAGE_KEY, JSON.stringify(user));
  safeStorageSet(TOKEN_STORAGE_KEY, user.token);
};

const mapAuthPayload = (payload: AuthPayload): User => ({
  id: payload.user.id,
  firstName: payload.user.first_name,
  email: payload.user.email,
  token: payload.user.api_token,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  useEffect(() => {
    const storedUser = loadStoredUser();
    setUser(storedUser);

    if (!storedUser) {
      setIsBootstrapping(false);
      return;
    }

    let cancelled = false;
    const validatingToken = storedUser.token;
    apiGet("/notifications/preferences")
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          const currentToken = safeStorageGet(TOKEN_STORAGE_KEY);
          if (currentToken === validatingToken) {
            clearStoredAuth();
            setUser(null);
          }
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsBootstrapping(false);
        }
      });

    return () => {
      cancelled = true;
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

  const login = async (email: string, password: string) => {
    const payload = await apiPost<AuthPayload>("/auth/login", { email, password });
    const nextUser = mapAuthPayload(payload);
    persistUser(nextUser);
    queryClient.clear();
    setUser(nextUser);
    dispatchAuthChanged();
    return nextUser;
  };

  const signup = async (firstName: string, email: string, password: string) => {
    const payload = await apiPost<AuthPayload>("/auth/signup", {
      first_name: firstName,
      email,
      password,
    });
    const nextUser = mapAuthPayload(payload);
    persistUser(nextUser);
    queryClient.clear();
    setUser(nextUser);
    dispatchAuthChanged();
    return nextUser;
  };

  const logout = () => {
    clearStoredAuth();
    queryClient.clear();
    setUser(null);
    dispatchAuthChanged();
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      login,
      signup,
      logout,
      isLoggedIn: !!user,
      isBootstrapping,
    }),
    [isBootstrapping, user]
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
