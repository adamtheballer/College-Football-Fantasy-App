import { useState } from "react";
import { LogOut, Menu } from "lucide-react";
import { Link } from "react-router-dom";

import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { navDomId, type ShellNavItem } from "./navigation";

type MobileNavigationProps = {
  items: ShellNavItem[];
  allItems: ShellNavItem[];
  pathname: string;
  onSignOut: () => void;
};

const displayNavName = (name: string) => name.toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase()).replace("Mock Draft", "Draft");

export function MobileNavigation({ items, allItems, pathname, onSignOut }: MobileNavigationProps) {
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const drawerItems = allItems.filter((item) => item.kind !== "danger");
  const signOutItem = allItems.find((item) => item.kind === "danger");
  const isMoreActive = drawerItems.some(
    (item) => item.path === pathname && !items.some((mobileItem) => mobileItem.name === item.name),
  );
  // Guests have three destinations; signed-in managers have four. Include the
  // More button in the grid calculation so neither state leaves a blank mobile
  // slot or packs the tabs unevenly to one side.
  const visibleItemCount = items.length + 1;

  return (
    <Sheet open={isMoreOpen} onOpenChange={setIsMoreOpen}>
      <nav
        aria-label="Primary mobile navigation"
        className={cn(
          "relative z-[170] mx-3 mb-[max(0.5rem,env(safe-area-inset-bottom))] mt-2 shrink-0 rounded-lg border border-cfb-border-subtle bg-cfb-sidebar p-1 shadow-sm transition-opacity lg:hidden",
          isMoreOpen && "pointer-events-none opacity-0",
        )}
      >
        <div
          data-mobile-nav-grid="true"
          className="grid gap-0.5"
          style={{ gridTemplateColumns: `repeat(${visibleItemCount}, minmax(0, 1fr))` }}
        >
          {items.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.path;

            return (
              <Link
                key={item.name}
                to={item.path}
                aria-label={item.badge ? `${item.name}: ${item.badge} unread chat messages` : item.name}
                className={cn(
                  "font-ui relative flex min-h-[56px] min-w-0 flex-col items-center justify-center gap-1 rounded-md px-0.5 text-[11px] font-bold uppercase tracking-[0.04em] leading-none transition-colors after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full after:bg-transparent",
                  isActive
                    ? "bg-cfb-brand/[0.12] text-cfb-text-primary after:bg-cfb-brand"
                    : "text-cfb-text-muted hover:bg-cfb-surface-hover/70 hover:text-cfb-text-primary",
                )}
              >
                <span className="relative inline-flex">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {item.badge ? (
                    <span
                      role="status"
                      aria-label={`${item.badge} unread chat messages`}
                      className="absolute -right-3 -top-2 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[8px] font-black text-white"
                    >
                      {item.badge}
                    </span>
                  ) : null}
                </span>
                <span className="max-w-full whitespace-nowrap">{displayNavName(item.name)}</span>
              </Link>
            );
          })}

          <button
            type="button"
            aria-label="Open all navigation"
            aria-expanded={isMoreOpen}
            onClick={() => setIsMoreOpen(true)}
            className={cn(
              "font-ui relative flex min-h-[56px] min-w-0 flex-col items-center justify-center gap-1 rounded-md px-0.5 text-[11px] font-bold uppercase tracking-[0.04em] leading-none transition-colors after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full after:bg-transparent",
              isMoreActive
                ? "bg-cfb-brand/[0.12] text-cfb-text-primary after:bg-cfb-brand"
                : "text-cfb-text-muted hover:bg-cfb-surface-hover/70 hover:text-cfb-text-primary",
            )}
          >
            <Menu className="h-4 w-4" aria-hidden="true" />
            <span className="whitespace-nowrap">More</span>
          </button>
        </div>
      </nav>

      <SheetContent
        side="right"
        className="z-[220] flex h-[100dvh] w-[min(22rem,calc(100vw-1rem))] flex-col overflow-hidden border-cfb-border-subtle bg-cfb-sidebar p-0 text-cfb-text-primary sm:max-w-none"
      >
        <SheetHeader className="border-b border-cfb-border-subtle px-6 pb-5 pt-7 text-left">
          <SheetTitle className="font-display text-2xl font-black tracking-[-0.04em] text-cfb-text-primary">
            All navigation
          </SheetTitle>
          <SheetDescription className="text-sm text-cfb-text-muted">
            Every league tool, one tap away.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          <div className="grid gap-2">
            {drawerItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.path;

              return (
                <SheetClose key={item.name} asChild>
                  <Link
                    to={item.path}
                    data-mobile-nav-item={navDomId(item.name)}
                    className={cn(
                      "font-ui flex min-h-[52px] items-center gap-4 rounded-md border px-4 py-3 text-sm font-bold uppercase tracking-[0.05em] transition-colors",
                      isActive
                        ? "border-cfb-brand/40 bg-cfb-brand/[0.10] text-cfb-text-primary"
                        : "border-transparent text-cfb-text-secondary hover:border-cfb-border-subtle hover:bg-cfb-surface-hover/70 hover:text-cfb-text-primary",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0 text-cfb-brand" aria-hidden="true" />
                    <span className="min-w-0 flex-1">{displayNavName(item.name)}</span>
                    {item.badge ? (
                      <span className="inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[9px] font-black tracking-normal text-white">
                        {item.badge}
                      </span>
                    ) : null}
                  </Link>
                </SheetClose>
              );
            })}
          </div>
        </div>

        {signOutItem ? (
          <div className="border-t border-cfb-border-subtle p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <button
              type="button"
              aria-label={signOutItem.name}
              onClick={() => {
                setIsMoreOpen(false);
                onSignOut();
              }}
              className="font-ui flex min-h-[52px] w-full items-center gap-4 rounded-md border border-cfb-danger/25 bg-cfb-danger/[0.06] px-4 py-3 text-left text-sm font-bold uppercase tracking-[0.05em] text-red-700 transition hover:bg-cfb-danger/[0.10]"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              {displayNavName(signOutItem.name)}
            </button>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
