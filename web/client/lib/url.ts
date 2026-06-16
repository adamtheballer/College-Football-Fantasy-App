const LOCALHOST_NAMES = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1"]);

export const LOCALHOST_INVITE_WARNING =
  "This invite link uses localhost, so it only works on this computer. To invite friends, expose your local app with a public tunnel or deploy it, then set PUBLIC_WEB_URL and VITE_PUBLIC_WEB_URL to that public URL.";

const parseUrl = (value: string): URL | null => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    const candidate = /^[a-z][a-z\d+\-.]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    return new URL(candidate);
  } catch {
    return null;
  }
};

export const isLocalhostUrl = (url: string): boolean => {
  const parsed = parseUrl(url);
  if (!parsed) return false;
  const hostname = parsed.hostname.toLowerCase();
  return LOCALHOST_NAMES.has(hostname) || hostname.startsWith("127.");
};

export const getPublicWebUrl = (): string => {
  const browserOrigin = typeof window !== "undefined" ? window.location.origin : "";
  const configured = import.meta.env.VITE_PUBLIC_WEB_URL || browserOrigin || "http://localhost:8080";
  return configured.replace(/\/+$/, "");
};

export const extractMockInviteToken = (value: string): string | null => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = parseUrl(trimmed);
  if (parsed) {
    const parts = parsed.pathname.split("/").filter(Boolean).map(decodeURIComponent);
    if (parts.length >= 4 && parts.slice(-4, -1).join("/") === "draft/mock/invite") {
      return parts[parts.length - 1] || null;
    }
    const code = parsed.searchParams.get("code");
    if (code) return code.trim() || null;
  }
  return trimmed;
};

export const getInviteLinkStatus = (inviteLink: string) =>
  isLocalhostUrl(inviteLink)
    ? { label: "Local-only link", isLocalOnly: true, warning: LOCALHOST_INVITE_WARNING }
    : { label: "Public invite link ready", isLocalOnly: false, warning: null };

export const copyInviteLinkToClipboard = async (inviteLink: string): Promise<boolean> => {
  if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
    return false;
  }
  await navigator.clipboard.writeText(inviteLink);
  return true;
};
