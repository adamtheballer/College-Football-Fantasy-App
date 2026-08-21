import { cva } from "class-variance-authority";

export const surfaceCardVariants = cva(
  "relative overflow-hidden border text-cfb-text-primary transition-colors duration-150",
  {
    variants: {
      variant: {
        default:
          "rounded-lg border-cfb-border-subtle bg-cfb-surface shadow-sm",
        raised:
          "rounded-lg border-cfb-border-subtle bg-cfb-surface-raised shadow-sm",
        interactive:
          "rounded-lg border-cfb-border-subtle bg-cfb-surface hover:border-cfb-border-strong hover:bg-cfb-surface-hover",
        scoreboard:
          "rounded-lg border-cfb-border-subtle bg-cfb-surface-raised shadow-sm",
        field:
          "rounded-lg border-cfb-border-subtle bg-cfb-surface shadow-sm",
      },
      padding: {
        none: "p-0",
        compact: "p-4",
        default: "p-4 sm:p-5",
        spacious: "p-5 sm:p-6",
      },
    },
    defaultVariants: {
      variant: "default",
      padding: "default",
    },
  },
);

export const statCardToneClasses = {
  neutral: {
    frame: "border-cfb-border-subtle bg-cfb-surface/90",
    label: "text-cfb-text-muted",
    value: "text-cfb-text-primary",
    accent: "bg-cfb-brand",
  },
  brand: {
    frame: "border-cfb-brand/30 bg-cfb-brand/[0.06]",
    label: "text-cfb-brand",
    value: "text-cfb-text-primary",
    accent: "bg-cfb-brand",
  },
  crimson: {
    frame: "border-cfb-crimson/30 bg-cfb-crimson/[0.06]",
    label: "text-cfb-crimson",
    value: "text-cfb-text-primary",
    accent: "bg-cfb-crimson",
  },
  gold: {
    frame: "border-cfb-gold/30 bg-cfb-gold/[0.06]",
    label: "text-cfb-gold",
    value: "text-cfb-text-primary",
    accent: "bg-cfb-gold",
  },
  success: {
    frame: "border-cfb-success/30 bg-cfb-success/[0.06]",
    label: "text-cfb-success",
    value: "text-cfb-text-primary",
    accent: "bg-cfb-success",
  },
  danger: {
    frame: "border-cfb-danger/30 bg-cfb-danger/[0.06]",
    label: "text-cfb-danger",
    value: "text-cfb-text-primary",
    accent: "bg-cfb-danger",
  },
} as const;

export type StatCardTone = keyof typeof statCardToneClasses;

export const statusBadgeClasses = {
  live: "border-score-live/30 bg-score-live/[0.08] text-emerald-800",
  projected: "border-score-projected/30 bg-score-projected/[0.08] text-blue-800",
  final: "border-score-final/30 bg-score-final/[0.08] text-slate-700",
  corrected: "border-score-corrected/30 bg-score-corrected/[0.08] text-violet-800",
  delayed: "border-score-delayed/35 bg-score-delayed/[0.08] text-amber-800",
  unavailable: "border-score-unavailable/30 bg-score-unavailable/[0.08] text-slate-600",
  locked: "border-score-locked/35 bg-score-locked/[0.08] text-orange-800",
  success: "border-cfb-success/30 bg-cfb-success/[0.08] text-emerald-800",
  warning: "border-cfb-warning/35 bg-cfb-warning/[0.08] text-amber-800",
  danger: "border-cfb-danger/35 bg-cfb-danger/[0.08] text-red-800",
  neutral: "border-cfb-border-subtle bg-cfb-surface-raised/75 text-cfb-text-secondary",
} as const;

export type StatusBadgeVariant = keyof typeof statusBadgeClasses;

export const statusBadgeLabels: Record<StatusBadgeVariant, string> = {
  live: "Live",
  projected: "Projected",
  final: "Final",
  corrected: "Corrected",
  delayed: "Delayed",
  unavailable: "Unavailable",
  locked: "Locked",
  success: "Success",
  warning: "Warning",
  danger: "Danger",
  neutral: "Status",
};

export const positionBadgeClasses = {
  QB: "border-blue-300/60 bg-blue-50 text-blue-800",
  RB: "border-emerald-300/60 bg-emerald-50 text-emerald-800",
  WR: "border-violet-300/60 bg-violet-50 text-violet-800",
  TE: "border-amber-300/60 bg-amber-50 text-amber-800",
  K: "border-cyan-300/60 bg-cyan-50 text-cyan-800",
  FLEX: "border-cfb-crimson/60 bg-cfb-crimson/[0.08] text-cfb-crimson",
  DST: "border-slate-300/60 bg-slate-50 text-slate-700",
  DEFAULT: "border-cfb-border-subtle bg-cfb-surface-raised/75 text-cfb-text-secondary",
} as const;

export type PositionBadgeKey = keyof typeof positionBadgeClasses;

export function getPositionBadgeClass(position?: string | null) {
  const normalized = String(position ?? "").trim().toUpperCase();
  if (normalized in positionBadgeClasses) {
    return positionBadgeClasses[normalized as PositionBadgeKey];
  }
  return positionBadgeClasses.DEFAULT;
}
