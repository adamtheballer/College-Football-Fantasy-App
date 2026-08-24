import { LogIn } from "lucide-react";
import { Link } from "react-router-dom";

import type { User } from "@/hooks/use-auth";
import { AppBrandLockup } from "./AppBrandLockup";

type TopBarProps = {
  isLoggedIn: boolean;
  user: User | null;
};

export function TopBar({ isLoggedIn, user }: TopBarProps) {
  return (
    <header
      id="app-header"
      className="sticky top-0 z-[120] border-b border-cfb-border-subtle bg-cfb-sidebar px-4 py-3 sm:px-6 lg:px-8"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <Link
            to="/"
            aria-label="College Fantasy Football"
            className="group relative inline-flex min-h-10 items-center rounded-md px-1 py-1 lg:hidden"
          >
            <AppBrandLockup variant="compact" />
          </Link>
        </div>
        <div className="hidden h-px flex-1 bg-cfb-border-subtle md:block" />
        <div className="flex shrink-0 items-center gap-3">
          {isLoggedIn ? (
            <div className="flex items-center gap-3">
              <span className="hidden text-sm font-semibold text-cfb-text-muted sm:inline">
                Dashboard
              </span>
              <div className="hidden h-1 w-1 rounded-full bg-cfb-border-strong sm:block" />
              <span className="text-sm font-semibold text-cfb-text-primary">
                Welcome <span className="text-cfb-brand">{user?.firstName ?? "Manager"}</span>
              </span>
            </div>
          ) : (
            <Link
              to="/login"
              className="inline-flex items-center gap-2 rounded-md bg-cfb-brand px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-cfb-brand-hover"
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
