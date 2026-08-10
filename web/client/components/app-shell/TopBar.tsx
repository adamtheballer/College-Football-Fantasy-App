import { LogIn } from "lucide-react";
import { Link } from "react-router-dom";

import type { User } from "@/hooks/use-auth";

type TopBarProps = {
  isLoggedIn: boolean;
  user: User | null;
};

export function TopBar({ isLoggedIn, user }: TopBarProps) {
  return (
    <header
      id="app-header"
      className="sticky top-0 z-[120] border-b border-cfb-border-subtle bg-cfb-canvas/95 px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] backdrop-blur-xl sm:px-6 sm:py-4 lg:px-8"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <Link
            to="/"
            aria-label="Early Access CFB Fantasy Beta"
            className="group relative inline-flex min-h-10 items-center rounded-xl px-1 py-1 lg:hidden"
          >
            <span
              aria-hidden="true"
              className="absolute -inset-x-2 -inset-y-1 rounded-full bg-[radial-gradient(ellipse_at_center,hsl(var(--brand-primary)/0.28),hsl(var(--accent-gold)/0.10)_42%,transparent_72%)] opacity-80 blur-md transition group-hover:opacity-100"
            />
            <span className="relative flex flex-col gap-0.5 leading-none">
              <span className="text-[8px] font-black uppercase tracking-[0.2em] text-cfb-gold/90">
                Early Access
              </span>
              <span className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="font-display text-lg font-black uppercase italic tracking-[-0.06em] text-cfb-text-primary">
                  CFB Fantasy
                </span>
                <span className="rounded-md border border-cfb-brand/50 bg-cfb-brand/[0.16] px-1.5 py-0.5 text-[7px] font-black uppercase tracking-[0.14em] text-cfb-cyan shadow-[0_0_14px_hsl(var(--brand-primary)/0.32)]">
                  Beta
                </span>
              </span>
            </span>
          </Link>
        </div>
        <div className="hidden h-px flex-1 bg-cfb-border-subtle md:block" />
        <div className="flex shrink-0 items-center gap-3">
          {isLoggedIn ? (
            <div className="flex items-center gap-3">
              <span className="hidden text-xs font-black uppercase tracking-[0.14em] text-cfb-text-muted sm:inline">
                Dashboard
              </span>
              <div className="hidden h-1 w-1 rounded-full bg-cfb-border-strong sm:block" />
              <span className="text-xs font-bold tracking-[0.04em] text-cfb-text-primary sm:font-black sm:uppercase sm:tracking-[0.12em]">
                Welcome <span className="text-cfb-brand">{user?.firstName ?? "Manager"}</span>
              </span>
            </div>
          ) : (
            <Link
              to="/login"
              className="inline-flex items-center gap-2 rounded-xl border border-cfb-brand/40 bg-cfb-brand/[0.16] px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-blue-50 transition hover:border-cfb-brand hover:bg-cfb-brand/[0.24]"
            >
              <LogIn className="h-3.5 w-3.5" aria-hidden="true" />
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
