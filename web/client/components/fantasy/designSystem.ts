import { cva } from "class-variance-authority";

export const surfaceCardVariants = cva(
  "relative overflow-hidden border text-cfb-text-primary transition-colors duration-200",
  {
    variants: {
      variant: {
        default:
          "rounded-xl border-cfb-border-subtle bg-cfb-surface shadow-[0_8px_20px_rgba(2,6,23,0.18)]",
        raised:
          "rounded-xl border-cfb-border-subtle bg-cfb-surface-raised shadow-[0_12px_26px_rgba(2,6,23,0.22)]",
        interactive:
          "rounded-xl border-cfb-border-subtle bg-cfb-surface shadow-[0_8px_20px_rgba(2,6,23,0.18)] hover:border-cfb-border-strong hover:bg-cfb-surface-hover",
        scoreboard:
          "rounded-xl border-cfb-border-subtle bg-cfb-surface-raised shadow-[0_12px_26px_rgba(0,0,0,0.18)]",
        field:
          "cfb-yard-lines rounded-xl border-cfb-border-subtle bg-cfb-surface shadow-[0_8px_20px_rgba(2,6,23,0.18)]",
      },
      padding: {
        none: "p-0",
        compact: "p-4",
        default: "p-5 sm:p-6",
        spacious: "p-6 sm:p-8",
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
    frame: "border-cfb-brand/40 bg-cfb-brand/10",
    label: "text-blue-200",
    value: "text-blue-100",
    accent: "bg-cfb-brand",
  },
  pink: {
    frame: "border-cfb-pink/35 bg-cfb-pink/10",
    label: "text-pink-200",
    value: "text-pink-100",
    accent: "bg-cfb-pink",
  },
  gold: {
    frame: "border-cfb-gold/35 bg-cfb-gold/10",
    label: "text-yellow-200",
    value: "text-yellow-100",
    accent: "bg-cfb-gold",
  },
  success: {
    frame: "border-cfb-success/35 bg-cfb-success/10",
    label: "text-emerald-200",
    value: "text-emerald-100",
    accent: "bg-cfb-success",
  },
  danger: {
    frame: "border-cfb-danger/35 bg-cfb-danger/10",
    label: "text-red-200",
    value: "text-red-100",
    accent: "bg-cfb-danger",
  },
} as const;

export type StatCardTone = keyof typeof statCardToneClasses;

export const statusBadgeClasses = {
  live: "border-score-live/35 bg-score-live/[0.12] text-emerald-100",
  projected: "border-score-projected/35 bg-score-projected/[0.12] text-blue-100",
  final: "border-score-final/35 bg-score-final/[0.12] text-slate-100",
  corrected: "border-score-corrected/35 bg-score-corrected/[0.12] text-violet-100",
  delayed: "border-score-delayed/40 bg-score-delayed/[0.14] text-yellow-100",
  unavailable: "border-score-unavailable/35 bg-score-unavailable/[0.12] text-slate-300",
  locked: "border-score-locked/40 bg-score-locked/[0.14] text-orange-100",
  success: "border-cfb-success/35 bg-cfb-success/[0.12] text-emerald-100",
  warning: "border-cfb-warning/40 bg-cfb-warning/[0.14] text-yellow-100",
  danger: "border-cfb-danger/40 bg-cfb-danger/[0.14] text-red-100",
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
  QB: "border-blue-300/45 bg-blue-500/[0.14] text-blue-100",
  RB: "border-emerald-300/45 bg-emerald-500/[0.14] text-emerald-100",
  WR: "border-violet-300/45 bg-violet-500/[0.14] text-violet-100",
  TE: "border-amber-300/45 bg-amber-500/[0.14] text-amber-100",
  K: "border-cyan-300/45 bg-cyan-500/[0.14] text-cyan-100",
  FLEX: "border-pink-300/45 bg-pink-500/[0.14] text-pink-100",
  DST: "border-slate-300/45 bg-slate-500/[0.14] text-slate-100",
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
