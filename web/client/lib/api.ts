import { dispatchAuthExpired } from "@/lib/auth-events";

const resolveDefaultApiBase = () => {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }
  const hostname = window.location.hostname || "127.0.0.1";
  const apiHost = hostname === "localhost" ? "127.0.0.1" : hostname;
  return `${window.location.protocol}//${apiHost}:8000`;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || resolveDefaultApiBase();

const ACCESS_TOKEN_STORAGE_KEY = "cfb_access_token";
const ACCESS_TOKEN_EXPIRES_AT_STORAGE_KEY = "cfb_access_token_expires_at";
const CSRF_COOKIE_NAME = "cfb_csrf_token";
const CSRF_HEADER_NAME = "X-CSRF-Token";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const buildUrl = (path: string, params?: Record<string, string | number | boolean | undefined>) => {
  const base = API_BASE.replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${base}${cleanPath}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      url.searchParams.set(key, String(value));
    });
  }
  return url.toString();
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

export const getStoredAccessToken = (): string | null =>
  safeStorageGet(ACCESS_TOKEN_STORAGE_KEY);

export const getStoredAccessTokenExpiresAt = (): string | null =>
  safeStorageGet(ACCESS_TOKEN_EXPIRES_AT_STORAGE_KEY);

export const storeAccessTokenSession = (
  accessToken: string,
  accessTokenExpiresAt: string
) => {
  safeStorageSet(ACCESS_TOKEN_STORAGE_KEY, accessToken);
  safeStorageSet(ACCESS_TOKEN_EXPIRES_AT_STORAGE_KEY, accessTokenExpiresAt);
};

export const clearAccessTokenSession = () => {
  safeStorageRemove(ACCESS_TOKEN_STORAGE_KEY);
  safeStorageRemove(ACCESS_TOKEN_EXPIRES_AT_STORAGE_KEY);
};

export const isStoredAccessTokenExpired = (bufferMs = 0): boolean => {
  const expiresAt = getStoredAccessTokenExpiresAt();
  if (!expiresAt) {
    return true;
  }
  const parsed = Date.parse(expiresAt);
  if (Number.isNaN(parsed)) {
    return true;
  }
  return parsed <= Date.now() + bufferMs;
};

const getCookieValue = (name: string): string | null => {
  if (typeof document === "undefined") return null;
  const encodedName = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(encodedName));
  if (!cookie) return null;
  return decodeURIComponent(cookie.slice(encodedName.length));
};

const buildCsrfHeaders = () => {
  const token = getCookieValue(CSRF_COOKIE_NAME);
  return token ? { [CSRF_HEADER_NAME]: token } : {};
};

type RefreshPayload = {
  access_token: string;
  access_token_expires_at: string;
};

type RefreshResult = "refreshed" | "auth-expired" | "unavailable";

let inflightRefresh: Promise<RefreshResult> | null = null;

const refreshAccessToken = async (): Promise<RefreshResult> => {
  if (inflightRefresh) {
    return inflightRefresh;
  }
  inflightRefresh = (async () => {
    try {
      const res = await fetch(buildUrl("/auth/refresh"), {
        method: "POST",
        credentials: "include",
        headers: {
          ...buildCsrfHeaders(),
        },
      });
      if (!res.ok) {
        clearAccessTokenSession();
        if (res.status === 401 || res.status === 403) {
          dispatchAuthExpired();
          return "auth-expired";
        }
        return "unavailable";
      }
      const payload = (await res.json()) as RefreshPayload;
      if (!payload.access_token || !payload.access_token_expires_at) {
        clearAccessTokenSession();
        dispatchAuthExpired();
        return "auth-expired";
      }
      storeAccessTokenSession(payload.access_token, payload.access_token_expires_at);
      return "refreshed";
    } catch {
      clearAccessTokenSession();
      return "unavailable";
    } finally {
      inflightRefresh = null;
    }
  })();
  return inflightRefresh;
};

const buildAuthHeaders = () => {
  const token = getStoredAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const buildError = async (res: Response) => {
  let detail: unknown = null;
  try {
    detail = await res.clone().json();
  } catch {
    try {
      detail = await res.text();
    } catch {
      detail = null;
    }
  }

  if (
    detail &&
    typeof detail === "object" &&
    "detail" in detail &&
    typeof detail.detail === "string"
  ) {
    return new ApiError(res.status, detail.detail, detail);
  }

  if (typeof detail === "string" && detail.trim()) {
    return new ApiError(res.status, detail, detail);
  }

  return new ApiError(res.status, `API ${res.status}: ${res.statusText}`, detail);
};

const parseJson = async <T>(res: Response): Promise<T> => {
  if (res.status === 204) {
    return null as T;
  }
  return res.json();
};

type RequestOptions = {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  params?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  signal?: AbortSignal;
  retryOn401?: boolean;
};

const apiRequest = async <T>({
  method,
  path,
  params,
  body,
  signal,
  retryOn401 = true,
}: RequestOptions): Promise<T> => {
  const headers: Record<string, string> = {
    ...buildAuthHeaders(),
  };
  if (method !== "GET") {
    Object.assign(headers, buildCsrfHeaders());
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      credentials: "include",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(
      0,
      `Unable to reach the backend API at ${API_BASE}. Make sure FastAPI is running and CORS allows this web origin.`,
      { cause: error instanceof Error ? error.message : String(error), apiBase: API_BASE }
    );
  }
  if (res.status === 401 && retryOn401 && !path.startsWith("/auth/")) {
    const refreshResult = await refreshAccessToken();
    if (refreshResult === "refreshed") {
      return apiRequest<T>({
        method,
        path,
        params,
        body,
        signal,
        retryOn401: false,
      });
    }
  }
  if (!res.ok) {
    throw await buildError(res);
  }
  return parseJson<T>(res);
};

export const apiGet = async <T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
  signal?: AbortSignal
): Promise<T> => {
  return apiRequest<T>({ method: "GET", path, params, signal });
};

export const apiPost = async <T>(
  path: string,
  body: unknown,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> => {
  return apiRequest<T>({ method: "POST", path, body, params });
};

export const apiPatch = async <T>(
  path: string,
  body: unknown,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> => {
  return apiRequest<T>({ method: "PATCH", path, body, params });
};

export const apiDelete = async <T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> => {
  return apiRequest<T>({ method: "DELETE", path, params });
};
