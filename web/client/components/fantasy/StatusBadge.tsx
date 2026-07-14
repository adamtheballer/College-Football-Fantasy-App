import * as React from "react";

import { cn } from "@/lib/utils";
import {
  statusBadgeClasses,
  statusBadgeLabels,
  type StatusBadgeVariant,
} from "./designSystem";

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: StatusBadgeVariant;
  showDot?: boolean;
}

export const StatusBadge = React.forwardRef<HTMLSpanElement, StatusBadgeProps>(
  ({ className, children, variant = "neutral", showDot = true, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-black uppercase tracking-[0.14em]",
        statusBadgeClasses[variant],
        className,
      )}
      {...props}
    >
      {showDot ? <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {children ?? statusBadgeLabels[variant]}
    </span>
  ),
);

StatusBadge.displayName = "StatusBadge";
