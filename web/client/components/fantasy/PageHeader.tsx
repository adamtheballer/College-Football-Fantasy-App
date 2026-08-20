import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type PageHeaderProps = {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

/** A compact, repeatable page introduction for data-heavy fantasy routes. */
export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <header className={cn("flex flex-col gap-4 border-b border-cfb-border-subtle pb-5 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="cfb-micro-label mb-2 text-cfb-brand">{eyebrow}</p> : null}
        <h1 className="cfb-display-title text-2xl sm:text-3xl">{title}</h1>
        {description ? <p className="cfb-body mt-2 max-w-2xl text-sm text-cfb-text-secondary">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}
