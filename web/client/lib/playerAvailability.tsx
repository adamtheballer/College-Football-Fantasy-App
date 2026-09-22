import type { ReactNode } from "react";

export type PlayerAvailabilityBadge = {
  code: "O" | "D" | "Q" | "P";
  label: "Out" | "Doubtful" | "Questionable" | "Probable";
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

const RED_BADGE = "border-red-300/45 bg-red-400/15 text-red-200";
const YELLOW_BADGE = "border-amber-200/45 bg-amber-300/15 text-amber-100";

/** Convert provider wording into distinct compact availability indicators. */
export function playerAvailabilityBadge(status?: string | null): PlayerAvailabilityBadge | null {
  const normalized = (status ?? "")
    .trim()
    .toUpperCase()
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ");

  if (ACTIVE_STATUSES.has(normalized)) return null;
  if (/\b(OUT|INACTIVE|IR|INJURED RESERVE|SUSPEND)/.test(normalized)) {
    return { code: "O", label: "Out", className: RED_BADGE };
  }
  if (/\bDOUBTFUL\b/.test(normalized)) {
    return { code: "D", label: "Doubtful", className: RED_BADGE };
  }
  if (/\bPROBABLE\b/.test(normalized)) {
    return { code: "P", label: "Probable", className: YELLOW_BADGE };
  }
  if (/\b(QUESTION|DAY TO DAY|GTD|GAME TIME|TBD)/.test(normalized)) {
    return { code: "Q", label: "Questionable", className: YELLOW_BADGE };
  }

  // Never hide an unfamiliar non-active report. Treat it as uncertain until
  // the availability ingestion normalizes the source wording.
  return { code: "Q", label: "Questionable", className: YELLOW_BADGE };
}

/** Keep the full card's dot color aligned with the row badge shown elsewhere. */
export function playerAvailabilityDotClass(status?: string | null) {
  const normalized = (status ?? "")
    .trim()
    .toUpperCase()
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ");

  if (["", "N/A", "NA", "NONE", "UNREPORTED"].includes(normalized)) return "bg-slate-300/70";
  if (ACTIVE_STATUSES.has(normalized)) return "bg-emerald-300";

  const badge = playerAvailabilityBadge(status);
  if (badge?.code === "O" || badge?.code === "D") return "bg-red-400";
  if (badge?.code === "Q" || badge?.code === "P") return "bg-amber-300";

  // Missing official information is not a verified active designation.
  return "bg-slate-300/70";
}

export function PlayerAvailabilityIndicator({ status, children, showActive = true }: { status?: string | null; children?: ReactNode; showActive?: boolean }) {
  const badge = playerAvailabilityBadge(status);
  if (!badge) {
    const normalized = (status ?? "").trim().toUpperCase();
    if (!showActive || !["ACTIVE", "AVAILABLE", "FULL", "HEALTHY"].includes(normalized)) return <>{children}</>;
    return (
      <span className="inline-flex min-w-0 items-center gap-1.5">
        {children}
        <span aria-label="Active" title="Active" className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-300" />
      </span>
    );
  }

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
