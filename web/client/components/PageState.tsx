import type { ReactNode } from "react";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type PageStateProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  children?: ReactNode;
  className?: string;
};

export function PageShell({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <main className={cn("relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8", className)}>
      {children}
    </main>
  );
}

export function PageLoadingState({
  title = "Loading",
  description = "Loading the latest data from the server.",
}: Partial<PageStateProps>) {
  return (
    <section
      role="status"
      aria-live="polite"
      className="rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/90 p-6 shadow-[0_24px_90px_rgba(14,165,233,0.12)]"
    >
      <div className="flex items-center gap-3 text-sky-100">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-300">{title}</p>
          <p className="mt-1 text-sm font-semibold text-slate-400">{description}</p>
        </div>
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-3" aria-hidden="true">
        <Skeleton className="h-24 rounded-3xl bg-sky-200/10" />
        <Skeleton className="h-24 rounded-3xl bg-sky-200/10" />
        <Skeleton className="h-24 rounded-3xl bg-sky-200/10" />
      </div>
    </section>
  );
}

export function PageEmptyState({
  eyebrow = "Empty State",
  title,
  description,
  actionLabel,
  onAction,
  children,
  className,
}: PageStateProps) {
  return (
    <section
      className={cn(
        "rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(13,23,39,0.96),rgba(16,30,52,0.9)_48%,rgba(15,23,42,0.96))] p-8 text-center shadow-[0_24px_90px_rgba(14,165,233,0.12)]",
        className
      )}
    >
      <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">{eyebrow}</p>
      <h2 className="mt-3 text-2xl font-black italic text-slate-50">{title}</h2>
      {description ? <p className="mx-auto mt-3 max-w-2xl text-sm font-semibold leading-6 text-slate-400">{description}</p> : null}
      {children ? <div className="mt-5">{children}</div> : null}
      {actionLabel && onAction ? (
        <Button type="button" onClick={onAction} className="mt-6 h-11 rounded-2xl px-6 text-[10px] font-black uppercase tracking-[0.18em]">
          {actionLabel}
        </Button>
      ) : null}
    </section>
  );
}

export function PageErrorState({
  title = "Unable to load this screen",
  description = "The request failed. Retry once the backend is reachable and your session is valid.",
  actionLabel = "Retry",
  onAction,
  className,
}: Partial<PageStateProps>) {
  return (
    <section
      role="alert"
      className={cn(
        "rounded-[2rem] border border-red-300/25 bg-red-500/10 p-8 text-center shadow-[0_24px_90px_rgba(248,113,113,0.12)]",
        className
      )}
    >
      <AlertTriangle className="mx-auto h-8 w-8 text-red-200" aria-hidden="true" />
      <h2 className="mt-4 text-2xl font-black italic text-red-50">{title}</h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm font-semibold leading-6 text-red-100/75">{description}</p>
      {onAction ? (
        <Button
          type="button"
          variant="outline"
          onClick={onAction}
          className="mt-6 h-11 rounded-2xl border-red-300/25 bg-red-500/10 px-6 text-[10px] font-black uppercase tracking-[0.18em] text-red-100 hover:bg-red-500/20"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {actionLabel}
        </Button>
      ) : null}
    </section>
  );
}

export function AuthExpiredState() {
  return (
    <PageShell>
      <PageErrorState
        title="Session expired"
        description="Sign in again to continue. Your local session was cleared because the backend rejected the auth token."
        actionLabel="Go to sign in"
        onAction={() => {
          window.location.assign("/login");
        }}
      />
    </PageShell>
  );
}
