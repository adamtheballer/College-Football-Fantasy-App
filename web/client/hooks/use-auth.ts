import { useState, useEffect } from "react";
import { apiPost } from "@/lib/api";

export interface User {
  firstName: string;
  email: string;
  token: string;
  id: number;
}

const AUTH_CHANGED_EVENT = "cfb-auth-changed";

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

const loadStoredUser = (): User | null => {
  const savedUser = safeStorageGet("cfb_user");
  if (!savedUser) return null;
  try {
    return JSON.parse(savedUser) as User;
  } catch {
    safeStorageRemove("cfb_user");
    safeStorageRemove("cfb_token");
    return null;
  }
};

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    setUser(loadStoredUser());

    const syncAuth = () => setUser(loadStoredUser());
    window.addEventListener("storage", syncAuth);
    window.addEventListener(AUTH_CHANGED_EVENT, syncAuth);
    return () => {
      window.removeEventListener("storage", syncAuth);
      window.removeEventListener(AUTH_CHANGED_EVENT, syncAuth);
    };
  }, []);

  const login = async (email: string, password: string) => {
    const payload = await apiPost<{ user: { id: number; first_name: string; email: string; api_token: string } }>(
      "/auth/login",
      { email, password }
    );
    const newUser = {
      id: payload.user.id,
      firstName: payload.user.first_name,
      email: payload.user.email,
      token: payload.user.api_token,
    };
    safeStorageSet("cfb_user", JSON.stringify(newUser));
    safeStorageSet("cfb_token", payload.user.api_token);
    setUser(newUser);
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
  };

  const signup = async (firstName: string, email: string, password: string) => {
    const payload = await apiPost<{ user: { id: number; first_name: string; email: string; api_token: string } }>(
      "/auth/signup",
      { first_name: firstName, email, password }
    );
    const newUser = {
      id: payload.user.id,
      firstName: payload.user.first_name,
      email: payload.user.email,
      token: payload.user.api_token,
    };
    safeStorageSet("cfb_user", JSON.stringify(newUser));
    safeStorageSet("cfb_token", payload.user.api_token);
    setUser(newUser);
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
  };

  const logout = () => {
    safeStorageRemove("cfb_user");
    safeStorageRemove("cfb_token");
    setUser(null);
    window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
  };

  return { user, login, signup, logout, isLoggedIn: !!user };
}
