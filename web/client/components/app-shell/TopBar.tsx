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
      className="sticky top-0 z-[120] border-b border-cfb-border-subtle bg-cfb-canvas/95 px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="hidden text-xs font-black uppercase tracking-[0.18em] text-cfb-text-muted sm:block">
            College Football Fantasy
          </p>
          <Link
            to="/"
            className="font-display text-lg font-black uppercase italic tracking-[-0.06em] text-cfb-text-primary lg:hidden"
          >
            CFB Fantasy
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
              <span className="text-xs font-black uppercase tracking-[0.12em] text-cfb-text-primary">
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
