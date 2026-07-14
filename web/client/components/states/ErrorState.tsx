import * as React from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ErrorStateProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title?: React.ReactNode;
  message: React.ReactNode;
  retryLabel?: string;
  onRetry?: () => void;
}

export const ErrorState = React.forwardRef<HTMLDivElement, ErrorStateProps>(
  ({ className, title = "Unable to load this view", message, retryLabel, onRetry, ...props }, ref) => (
    <div
      ref={ref}
      role="alert"
      className={cn(
        "rounded-2xl border border-cfb-danger/35 bg-cfb-danger/10 p-5 text-left",
        className,
      )}
      {...props}
    >
      <div className="flex gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-cfb-danger/35 bg-cfb-danger/15 text-red-100">
          <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <h2 className="font-black text-red-100">{title}</h2>
          <p className="mt-1 text-sm font-medium text-red-100/80">{message}</p>
          {retryLabel && onRetry ? (
            <Button type="button" variant="outline" size="sm" className="mt-4" onClick={onRetry}>
              {retryLabel}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  ),
);

ErrorState.displayName = "ErrorState";
