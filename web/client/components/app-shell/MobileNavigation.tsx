import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { type ShellNavItem } from "./navigation";

type MobileNavigationProps = {
  items: ShellNavItem[];
  pathname: string;
};

export function MobileNavigation({ items, pathname }: MobileNavigationProps) {
  return (
    <nav
      aria-label="Primary mobile navigation"
      className="fixed inset-x-3 bottom-3 z-[170] rounded-2xl border border-cfb-border-subtle bg-cfb-sidebar/95 p-1.5 shadow-[0_18px_45px_rgba(2,6,23,0.45)] backdrop-blur-xl lg:hidden"
    >
      <div className="grid grid-cols-5 gap-1">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.path;

          return (
            <Link
              key={item.name}
              to={item.path}
              aria-label={item.badge ? `${item.name}: ${item.badge} unread chat messages` : item.name}
              className={cn(
                "flex min-h-[58px] flex-col items-center justify-center gap-1 rounded-xl px-2 text-[9px] font-black uppercase tracking-[0.08em] transition-colors",
                isActive
                  ? "bg-cfb-brand text-white shadow-[0_0_24px_hsl(var(--brand-primary)/0.24)]"
                  : "text-cfb-text-muted hover:bg-cfb-surface-hover/70 hover:text-cfb-text-primary",
              )}
            >
              <span className="relative inline-flex">
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.badge ? (
                  <span
                    role="status"
                    aria-label={`${item.badge} unread chat messages`}
                    className="absolute -right-3 -top-2 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[8px] font-black text-white shadow-[0_0_12px_rgba(239,68,68,0.42)]"
                  >
                    {item.badge}
                  </span>
                ) : null}
              </span>
              <span className="max-w-full truncate">
                {item.name.replace("MOCK ", "")}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
