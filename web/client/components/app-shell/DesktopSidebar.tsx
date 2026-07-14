import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { navDomId, type ShellNavItem } from "./navigation";

type DesktopSidebarProps = {
  items: ShellNavItem[];
  pathname: string;
  onSignOut: () => void;
};

export function DesktopSidebar({ items, pathname, onSignOut }: DesktopSidebarProps) {
  return (
    <aside className="relative z-10 hidden h-screen w-72 shrink-0 overflow-hidden border-r border-cfb-border-subtle bg-cfb-sidebar shadow-[inset_-1px_0_0_hsl(var(--border-subtle)/0.9),18px_0_70px_rgba(2,6,23,0.28)] lg:sticky lg:top-0 lg:flex lg:flex-col">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_9%,hsl(var(--brand-primary)/0.16),transparent_34%),radial-gradient(circle_at_88%_76%,hsl(var(--accent-pink)/0.07),transparent_36%),linear-gradient(180deg,hsl(var(--background-surface-raised)/0.34),transparent_52%)]" />
      <div className="pointer-events-none absolute inset-y-10 right-0 w-px bg-gradient-to-b from-transparent via-cfb-border-strong/70 to-transparent" />

      <div className="relative z-10 p-8">
        <Link to="/" className="group inline-flex flex-col">
          <span className="font-display text-[1.75rem] font-black uppercase italic tracking-[-0.08em] text-cfb-text-primary transition group-hover:text-white">
            CFB Fantasy
          </span>
          <span className="mt-1 text-[10px] font-black uppercase tracking-[0.22em] text-cfb-brand">
            College Football
          </span>
        </Link>
      </div>

      <nav className="relative z-10 flex flex-1 flex-col justify-between overflow-hidden px-5 pb-8 pt-3">
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
                "group relative flex min-h-[56px] w-full items-center gap-4 rounded-xl border px-4 py-3 text-left font-sans text-[12px] font-black uppercase tracking-[0.10em] transition-all duration-200",
                isSignOut
                  ? "border-transparent text-red-200/50 hover:border-cfb-danger/45 hover:bg-cfb-danger/[0.12] hover:text-red-100"
                  : isAuth
                    ? "border-cfb-border-subtle/60 bg-cfb-surface-raised/25 text-cfb-text-secondary hover:border-cfb-brand/55 hover:bg-cfb-brand/[0.16] hover:text-white focus-visible:border-cfb-brand/55 focus-visible:bg-cfb-brand/[0.16] focus-visible:text-white"
                    : isActive
                      ? "border-cfb-brand/50 bg-cfb-brand/[0.14] text-white shadow-[inset_3px_0_0_hsl(var(--brand-primary)),0_0_30px_hsl(var(--brand-primary)/0.14)]"
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
              <span>{item.name}</span>
              {isActive && !isSignOut && !isAuth ? (
                <div
                  aria-hidden="true"
                  className="nav-active-overlay pointer-events-none absolute inset-0 rounded-xl bg-[radial-gradient(circle_at_22%_50%,hsl(var(--brand-primary)/0.16),transparent_58%)]"
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
