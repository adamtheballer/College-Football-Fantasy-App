import * as React from "react";

import { cn } from "@/lib/utils";
import { statCardToneClasses, type StatCardTone } from "./designSystem";

export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: React.ReactNode;
  value: React.ReactNode;
  helper?: React.ReactNode;
  tone?: StatCardTone;
}

export const StatCard = React.forwardRef<HTMLDivElement, StatCardProps>(
  ({ className, label, value, helper, tone = "neutral", ...props }, ref) => {
    const toneClasses = statCardToneClasses[tone];

    return (
      <div
        ref={ref}
        className={cn(
          "relative overflow-hidden rounded-2xl border p-5",
          toneClasses.frame,
          className,
        )}
        {...props}
      >
        <div
          aria-hidden="true"
          className={cn("absolute left-0 top-0 h-full w-1", toneClasses.accent)}
        />
        <div className={cn("cfb-micro-label", toneClasses.label)}>{label}</div>
        <div className={cn("mt-2 font-display text-4xl font-black tracking-[-0.05em]", toneClasses.value)}>
          {value}
        </div>
        {helper ? (
          <div className="mt-2 text-sm font-medium text-cfb-text-secondary">{helper}</div>
        ) : null}
      </div>
    );
  },
);

StatCard.displayName = "StatCard";
