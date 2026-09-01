import { cva } from "class-variance-authority";

export const surfaceCardVariants = cva(
  "relative overflow-hidden border text-cfb-text-primary transition-colors duration-150",
  {
    variants: {
      variant: {
        default:
          "rounded-md border-cfb-border-subtle bg-cfb-surface",
        raised:
          "rounded-md border-cfb-border-subtle bg-cfb-surface-raised",
        interactive:
          "rounded-md border-cfb-border-subtle bg-cfb-surface hover:border-cfb-border-strong hover:bg-cfb-surface-hover",
        scoreboard:
          "rounded-md border-cfb-border-subtle bg-cfb-surface-raised",
        field:
          "rounded-md border-cfb-border-subtle bg-cfb-surface",
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
  live: "border-score-live/35 bg-score-live/[0.10] text-emerald-200",
  projected: "border-score-projected/35 bg-score-projected/[0.10] text-blue-200",
  final: "border-score-final/35 bg-score-final/[0.10] text-slate-200",
  corrected: "border-score-corrected/35 bg-score-corrected/[0.10] text-violet-200",
  delayed: "border-score-delayed/40 bg-score-delayed/[0.10] text-amber-200",
  unavailable: "border-score-unavailable/35 bg-score-unavailable/[0.10] text-slate-300",
  locked: "border-score-locked/40 bg-score-locked/[0.10] text-orange-200",
  success: "border-cfb-success/35 bg-cfb-success/[0.10] text-emerald-200",
  warning: "border-cfb-warning/40 bg-cfb-warning/[0.10] text-amber-200",
  danger: "border-cfb-danger/35 bg-cfb-danger/[0.10] text-red-200",
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
  QB: "border-blue-300/35 bg-blue-400/[0.10] text-blue-200",
  RB: "border-emerald-300/35 bg-emerald-400/[0.10] text-emerald-200",
  WR: "border-violet-300/35 bg-violet-400/[0.10] text-violet-200",
  TE: "border-amber-300/35 bg-amber-400/[0.10] text-amber-200",
  K: "border-cyan-300/35 bg-cyan-400/[0.10] text-cyan-200",
  FLEX: "border-cfb-crimson/60 bg-cfb-crimson/[0.08] text-cfb-crimson",
  DST: "border-slate-300/35 bg-slate-200/[0.10] text-slate-200",
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
