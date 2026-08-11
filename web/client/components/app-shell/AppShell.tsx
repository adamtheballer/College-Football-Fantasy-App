import * as React from "react";

import { BackgroundEffects, collegiateCanvasBackground } from "@/components/BackgroundEffects";
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

export function shouldShowHomeHeader(pathname: string, hideChrome: boolean) {
  return !hideChrome && pathname === "/";
}

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
  // The Early Access lockup and manager greeting are home-dashboard context,
  // not global navigation. Keeping them off data-heavy league routes returns
  // meaningful vertical space on phones without removing the persistent nav.
  const showHomeHeader = shouldShowHomeHeader(pathname, hideChrome);

  return (
    <div
      className={cn(
        "isolate relative flex h-[100dvh] min-h-0 flex-col overflow-hidden bg-cfb-canvas font-sans text-cfb-text-primary selection:bg-cfb-brand/30 selection:text-white lg:h-screen lg:flex-row",
      )}
      style={{
        background: collegiateCanvasBackground,
      }}
    >
      {!hideDecor ? <BackgroundEffects /> : null}
      {!hideFloatingActions ? <FloatingQuickActions /> : null}

      {!hideChrome ? (
        <DesktopSidebar
          items={navItems}
          pathname={pathname}
          onSignOut={onSignOut}
        />
      ) : null}

      <main
        ref={mainScrollRef}
        data-app-scroll="true"
        data-scroll-owner={fixedViewport ? "draft-room" : "page"}
        className={cn(
          "relative z-10 flex min-h-0 min-w-0 flex-1 flex-col lg:h-full",
          fixedViewport
            ? "overflow-hidden"
            : "overflow-y-auto overscroll-y-contain touch-pan-y",
        )}
      >
        {showHomeHeader ? <TopBar isLoggedIn={isLoggedIn} user={user} /> : null}

        <div
          className={cn(
            "flex-1",
            compactContent
              ? "p-0"
              : "px-4 py-4 pb-5 sm:px-6 sm:py-6 sm:pb-6 lg:p-8",
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
