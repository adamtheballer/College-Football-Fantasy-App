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
  fixedViewport: boolean;
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
  fixedViewport,
  onSignOut,
  mainScrollRef,
}: AppShellProps) {
  const mobileNavItems = getMobileNavItems(navItems);

  return (
    <div
      className={cn(
        "isolate relative flex h-[100dvh] min-h-0 overflow-hidden bg-cfb-canvas font-sans text-cfb-text-primary selection:bg-cfb-brand/30 selection:text-white lg:h-screen",
        isLoggedIn ? "bg-[#0b0d10]" : "cfb-school-grid",
      )}
    >
      {!hideDecor ? <BackgroundEffects /> : null}
      {!hideFloatingActions ? <FloatingQuickActions /> : null}

      {!hideChrome ? (
        <DesktopSidebar items={navItems} pathname={pathname} onSignOut={onSignOut} />
      ) : null}

      <main
        ref={mainScrollRef}
        data-app-scroll="true"
        data-scroll-owner={fixedViewport ? "draft-room" : "page"}
        className={cn(
          "relative z-10 flex h-full min-h-0 min-w-0 flex-1 flex-col",
          fixedViewport
            ? "overflow-hidden"
            : "overflow-y-auto overscroll-y-contain touch-pan-y",
        )}
      >
        {!hideChrome ? <TopBar isLoggedIn={isLoggedIn} user={user} /> : null}

        <div
          className={cn(
            "flex-1",
            compactContent ? "p-0" : "px-4 py-4 pb-[calc(env(safe-area-inset-bottom)+5.5rem)] sm:px-6 sm:py-6 sm:pb-24 lg:p-8",
          )}
        >
          {children}
        </div>
      </main>

      {!hideChrome && mobileNavItems.length > 0 ? (
        <MobileNavigation
          items={mobileNavItems}
          allItems={navItems}
          pathname={pathname}
          onSignOut={onSignOut}
        />
      ) : null}
    </div>
  );
}
