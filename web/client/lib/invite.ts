const INVITE_CODE_PATTERN = /[A-Z0-9]{6,30}/;

export function normalizeInviteCode(value: string | null | undefined): string {
  return (value ?? "").trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
}

export function extractInviteCodeFromInput(value: string | null | undefined): string {
  const raw = (value ?? "").trim();
  if (!raw) return "";

  try {
    const url = new URL(raw);
    const joinMatch = url.pathname.match(/\/join\/([^/?#]+)/i);
    if (joinMatch?.[1]) {
      return normalizeInviteCode(decodeURIComponent(joinMatch[1]));
    }
    const queryCode = url.searchParams.get("invite_code") || url.searchParams.get("code");
    if (queryCode) {
      return normalizeInviteCode(queryCode);
    }
  } catch {
    // Treat non-URL values as invite code text.
  }

  const normalized = normalizeInviteCode(raw);
  const match = normalized.match(INVITE_CODE_PATTERN);
  return match ? match[0] : normalized;
}

export function buildLeagueInviteLink(code: string, origin?: string): string {
  const normalizedCode = normalizeInviteCode(code);
  const baseOrigin =
    origin ||
    (typeof window !== "undefined" && window.location.origin
      ? window.location.origin
      : "http://localhost:8080");
  return `${baseOrigin.replace(/\/+$/, "")}/join/${normalizedCode}`;
}
