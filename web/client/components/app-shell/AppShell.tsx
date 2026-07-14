import * as React from "react";

import { BackgroundEffects } from "@/components/BackgroundEffects";
import { FloatingQuickActions } from "@/components/FloatingQuickActions";
import type { User } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import { DesktopSidebar } from "./DesktopSidebar";
import { MobileNavigation } from "./MobileNavigation";
import { TopBar } from "./TopBar";
import { getMobileNavItems, type ShellNavItem } from "./navigation";

type AppShellProps = {
  children: React.ReactNode;
  navItems: ShellNavItem[];
  pathname: string;
  user: User | null;
  isLoggedIn: boolean;
  hideChrome: boolean;
  hideDecor: boolean;
  hideFloatingActions: boolean;
  compactContent: boolean;
  onSignOut: () => void;
  mainScrollRef: React.RefObject<HTMLElement>;
};

export function AppShell({
  children,
  navItems,
  pathname,
  user,
  isLoggedIn,
  hideChrome,
  hideDecor,
  hideFloatingActions,
  compactContent,
  onSignOut,
  mainScrollRef,
}: AppShellProps) {
  const mobileNavItems = getMobileNavItems(navItems);

  return (
    <div className="cfb-school-grid isolate relative flex h-screen overflow-hidden bg-cfb-canvas font-sans text-cfb-text-primary selection:bg-cfb-brand/30 selection:text-white">
      {!hideDecor ? <BackgroundEffects /> : null}
      {!hideFloatingActions ? <FloatingQuickActions /> : null}

      {!hideChrome ? (
        <DesktopSidebar items={navItems} pathname={pathname} onSignOut={onSignOut} />
      ) : null}

      <main
        ref={mainScrollRef}
        data-app-scroll="true"
        className="relative z-10 flex h-screen min-w-0 flex-1 flex-col overflow-y-auto"
      >
        {!hideChrome ? <TopBar isLoggedIn={isLoggedIn} user={user} /> : null}

        <div
          className={cn(
            "flex-1",
            compactContent ? "p-0" : "px-4 py-5 pb-28 sm:px-6 lg:p-8",
          )}
        >
          {children}
        </div>
      </main>

      {!hideChrome && mobileNavItems.length > 0 ? (
        <MobileNavigation items={mobileNavItems} pathname={pathname} />
      ) : null}
    </div>
  );
}
