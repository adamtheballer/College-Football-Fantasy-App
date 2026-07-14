import * as React from "react";

import { cn } from "@/lib/utils";
import { getPositionBadgeClass } from "./designSystem";

export interface PositionBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  position?: string | null;
}

export const PositionBadge = React.forwardRef<HTMLSpanElement, PositionBadgeProps>(
  ({ className, children, position, ...props }, ref) => {
    const label = children ?? (position ? String(position).toUpperCase() : "N/A");

    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex min-w-10 items-center justify-center rounded-full border px-2.5 py-1 text-[11px] font-black uppercase tracking-[0.12em]",
          getPositionBadgeClass(position),
          className,
        )}
        {...props}
      >
        {label}
      </span>
    );
  },
);

PositionBadge.displayName = "PositionBadge";
