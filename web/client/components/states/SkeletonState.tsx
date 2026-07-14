import * as React from "react";

import { cn } from "@/lib/utils";

export interface SkeletonStateProps extends React.HTMLAttributes<HTMLDivElement> {
  rows?: number;
}

export const SkeletonState = React.forwardRef<HTMLDivElement, SkeletonStateProps>(
  ({ className, rows = 3, ...props }, ref) => (
    <div ref={ref} className={cn("space-y-3", className)} {...props}>
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="h-14 animate-pulse rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised/55"
        />
      ))}
    </div>
  ),
);

SkeletonState.displayName = "SkeletonState";
