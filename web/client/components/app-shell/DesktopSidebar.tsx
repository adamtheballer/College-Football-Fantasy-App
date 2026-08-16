import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { AppBrandLockup } from "./AppBrandLockup";
import { navDomId, type ShellNavItem } from "./navigation";

type DesktopSidebarProps = {
  items: ShellNavItem[];
  pathname: string;
  onSignOut: () => void;
};

const displayNavName = (name: string) => name.toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase()).replace("Mock Draft", "Draft");

export function DesktopSidebar({ items, pathname, onSignOut }: DesktopSidebarProps) {
  return (
    <aside className="relative z-10 hidden h-screen w-64 shrink-0 overflow-hidden border-r border-cfb-border-subtle bg-cfb-sidebar lg:sticky lg:top-0 lg:flex lg:flex-col">

      <div className="relative z-10 border-b border-cfb-border-subtle p-6">
        <Link
          to="/"
          aria-label="Early Access CFB Fantasy Beta"
          className="group relative inline-flex min-h-14 items-center rounded-xl px-1 py-1"
        >
          <AppBrandLockup variant="desktop" />
        </Link>
      </div>

      <nav className="relative z-10 flex flex-1 flex-col justify-between overflow-hidden px-3 pb-5 pt-4">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.path;
          const isSignOut = item.kind === "danger";
          const isAuth = item.kind === "auth";
          const isAdmin = item.kind === "admin";
          const content = (
            <div
              id={navDomId(item.name)}
              data-nav-item="true"
              data-nav-active={isActive ? "true" : "false"}
              className={cn(
                "group relative flex min-h-[48px] w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left font-sans text-sm font-semibold transition-colors duration-150",
                isSignOut
                  ? "border-transparent text-red-200/50 hover:border-cfb-danger/45 hover:bg-cfb-danger/[0.12] hover:text-red-100"
                  : isAuth
                    ? "border-cfb-border-subtle/60 bg-cfb-surface-raised/25 text-cfb-text-secondary hover:border-cfb-brand/55 hover:bg-cfb-brand/[0.16] hover:text-white focus-visible:border-cfb-brand/55 focus-visible:bg-cfb-brand/[0.16] focus-visible:text-white"
                    : isActive
                      ? "border-cfb-brand/50 bg-cfb-brand/[0.14] text-white shadow-[inset_3px_0_0_hsl(var(--brand-primary))]"
                      : isAdmin
                        ? "border-cfb-gold/15 text-cfb-text-secondary hover:border-cfb-gold/40 hover:bg-cfb-gold/10 hover:text-yellow-100"
                        : "border-transparent text-cfb-text-muted hover:border-cfb-border-subtle hover:bg-cfb-surface-hover/55 hover:text-cfb-text-primary",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 transition-colors duration-200",
                  isSignOut
                    ? "text-red-200/50 group-hover:text-red-100"
                    : isAuth
                      ? "text-cfb-brand/70 group-hover:text-cfb-brand"
                    : isActive
                      ? "text-cfb-brand"
                      : "text-cfb-text-muted group-hover:text-cfb-text-primary",
                )}
              />
              <span>{displayNavName(item.name)}</span>
              {item.badge ? (
                <span
                  role="status"
                  aria-label={`${item.badge} unread chat messages`}
                  className="ml-auto inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 py-0.5 text-[9px] font-black tracking-normal text-white shadow-[0_0_14px_rgba(239,68,68,0.42)]"
                >
                  {item.badge}
                </span>
              ) : null}
              {isActive && !isSignOut && !isAuth ? (
                <div
                  aria-hidden="true"
                  className="nav-active-overlay pointer-events-none absolute inset-0 rounded-lg bg-cfb-brand/[0.04]"
                />
              ) : null}
            </div>
          );

          if (isSignOut) {
            return (
              <button key={item.name} type="button" onClick={onSignOut} className="w-full">
                {content}
              </button>
            );
          }

          return (
            <Link key={item.name} to={item.path} className="w-full">
              {content}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
