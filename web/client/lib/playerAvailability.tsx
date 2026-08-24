import type { ReactNode } from "react";

export type PlayerAvailabilityBadge = {
  code: "O" | "Q";
  label: "Out" | "Questionable";
  className: string;
};

const ACTIVE_STATUSES = new Set([
  "",
  "ACTIVE",
  "AVAILABLE",
  "FULL",
  "HEALTHY",
  "N/A",
  "NA",
  "NONE",
  "UNREPORTED",
]);

/** Convert provider wording into the two compact availability indicators. */
export function playerAvailabilityBadge(status?: string | null): PlayerAvailabilityBadge | null {
  const normalized = (status ?? "")
    .trim()
    .toUpperCase()
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ");

  if (ACTIVE_STATUSES.has(normalized)) return null;
  if (/\b(OUT|INACTIVE|IR|INJURED RESERVE|SUSPEND)/.test(normalized)) {
    return { code: "O", label: "Out", className: "border-red-300/45 bg-red-400/15 text-red-200" };
  }
  if (/\b(QUESTION|DOUBTFUL|DAY TO DAY|GTD|GAME TIME|PROBABLE|TBD)/.test(normalized)) {
    return { code: "Q", label: "Questionable", className: "border-amber-200/45 bg-amber-300/15 text-amber-100" };
  }

  // Never hide an unfamiliar non-active report. Treat it as uncertain until
  // the availability ingestion normalizes the source wording.
  return { code: "Q", label: "Questionable", className: "border-amber-200/45 bg-amber-300/15 text-amber-100" };
}

export function PlayerAvailabilityIndicator({ status, children }: { status?: string | null; children?: ReactNode }) {
  const badge = playerAvailabilityBadge(status);
  if (!badge) return <>{children}</>;

  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      {children}
      <span
        aria-label={badge.label}
        title={badge.label}
        className={`inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full border px-1 text-[9px] font-black leading-none ${badge.className}`}
      >
        {badge.code}
      </span>
    </span>
  );
}
