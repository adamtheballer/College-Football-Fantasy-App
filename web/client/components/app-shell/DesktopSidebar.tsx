import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { AppBrandLockup } from "./AppBrandLockup";
import { navDomId, type ShellNavItem } from "./navigation";

type DesktopSidebarProps = {
  items: ShellNavItem[];
  pathname: string;
  onSignOut: () => void;
};

const displayNavName = (name: string) => name.toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());

export function DesktopSidebar({ items, pathname, onSignOut }: DesktopSidebarProps) {
  return (
    <aside className="relative z-10 hidden h-screen w-64 shrink-0 overflow-hidden border-r border-cfb-border-subtle bg-cfb-sidebar lg:sticky lg:top-0 lg:flex lg:flex-col">

      <div className="relative z-10 border-b border-cfb-border-subtle p-6">
        <Link
          to="/"
          aria-label="College Fantasy Football"
          className="group relative inline-flex min-h-12 items-center rounded-md px-1 py-1"
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
                "group relative flex min-h-[44px] w-full items-center gap-3 rounded-md border px-3 py-2 text-left font-ui text-sm font-bold uppercase tracking-[0.06em] transition-colors duration-150",
                isSignOut
                  ? "border-transparent text-red-700 hover:border-cfb-danger/30 hover:bg-cfb-danger/[0.06] hover:text-red-800"
                  : isAuth
                    ? "border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-secondary hover:border-cfb-brand/55 hover:bg-cfb-brand/[0.08] hover:text-cfb-text-primary focus-visible:border-cfb-brand/55 focus-visible:bg-cfb-brand/[0.08]"
                    : isActive
                      ? "border-cfb-brand/25 bg-cfb-brand/[0.08] text-cfb-text-primary shadow-[inset_3px_0_0_hsl(var(--brand-primary))]"
                      : isAdmin
                        ? "border-cfb-gold/20 text-cfb-text-secondary hover:border-cfb-gold/40 hover:bg-cfb-gold/[0.08] hover:text-cfb-text-primary"
                        : "border-transparent text-cfb-text-muted hover:border-cfb-border-subtle hover:bg-cfb-surface-hover/55 hover:text-cfb-text-primary",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 transition-colors duration-200",
                  isSignOut
                    ? "text-red-500 group-hover:text-red-700"
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
                  className="ml-auto inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1.5 py-0.5 text-[9px] font-black tracking-normal text-white"
                >
                  {item.badge}
                </span>
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
