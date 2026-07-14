import * as React from "react";
import { CircleOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface EmptyStateProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title: React.ReactNode;
  description?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  ({ className, title, description, actionLabel, onAction, icon, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-2xl border border-dashed border-cfb-border-subtle bg-cfb-surface/65 p-6 text-center",
        className,
      )}
      {...props}
    >
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full border border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-secondary">
        {icon ?? <CircleOff className="h-5 w-5" aria-hidden="true" />}
      </div>
      <h2 className="mt-4 text-lg font-black text-cfb-text-primary">{title}</h2>
      {description ? (
        <p className="mx-auto mt-2 max-w-xl text-sm font-medium text-cfb-text-secondary">
          {description}
        </p>
      ) : null}
      {actionLabel && onAction ? (
        <Button type="button" className="mt-5" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  ),
);

EmptyState.displayName = "EmptyState";
