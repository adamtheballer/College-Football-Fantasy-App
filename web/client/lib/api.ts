const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

const getAuthHeaders = () => {
  let token: string | null = null;
  try {
    token = localStorage.getItem("cfb_token");
  } catch {
    token = null;
  }
  return token ? { "X-User-Token": token } : {};
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

export const apiGet = async <T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
  signal?: AbortSignal
): Promise<T> => {
  const res = await fetch(buildUrl(path, params), { signal, headers: getAuthHeaders() });
  if (!res.ok) {
    throw await buildError(res);
  }
  return parseJson<T>(res);
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
    throw await buildError(res);
  }
  return parseJson<T>(res);
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
    throw await buildError(res);
  }
  return parseJson<T>(res);
};
