const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

const getAuthHeaders = () => {
  let token: string | null = null;
  try {
    token = localStorage.getItem("cfb_token");
  } catch {
    token = null;
  }
  return token ? { "X-User-Token": token } : {};
};

export const apiGet = async <T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
  signal?: AbortSignal
): Promise<T> => {
  const res = await fetch(buildUrl(path, params), { signal, headers: getAuthHeaders() });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
};

export const apiPost = async <T>(
  path: string,
  body: unknown,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> => {
  const res = await fetch(buildUrl(path, params), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
};

export const apiPatch = async <T>(
  path: string,
  body: unknown,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> => {
  const res = await fetch(buildUrl(path, params), {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
};
