import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { AppOnboardingTour } from "./AppOnboardingTour";
import { AppShell } from "./app-shell/AppShell";
import {
  getShellNavItems,
  isAuthFlowRoute,
  isCreateLeagueRoute,
  isDraftRoomRoute,
} from "./app-shell/navigation";
import { useAuth } from "@/hooks/use-auth";
import { clearPendingGuide, hasPendingGuide } from "@/lib/onboarding";

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, isLoggedIn } = useAuth();
  const [isGuideActive, setIsGuideActive] = useState(false);
  const mainScrollRef = useRef<HTMLElement | null>(null);

  const navItems = useMemo(
    () => getShellNavItems(user, isLoggedIn),
    [isLoggedIn, user],
  );

  const isDraftRoomPage = isDraftRoomRoute(location.pathname);
  const isCreateLeaguePage = isCreateLeagueRoute(location.pathname);
  const isAuthFlowPage = isAuthFlowRoute(location.pathname);

  useEffect(() => {
    if (!user) {
      setIsGuideActive(false);
      return;
    }

    if (isAuthFlowPage) {
      setIsGuideActive(false);
      return;
    }

    const shouldStartGuide = hasPendingGuide(user.id);
    if (!shouldStartGuide) {
      clearPendingGuide(user.id);
      setIsGuideActive(false);
      return;
    }

    if (location.pathname !== "/") {
      navigate("/", { replace: true });
      return;
    }

    if (mainScrollRef.current) {
      mainScrollRef.current.scrollTo({ top: 0, left: 0, behavior: "auto" });
    } else {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
    clearPendingGuide(user.id);
    setIsGuideActive(true);
  }, [isAuthFlowPage, location.pathname, navigate, user]);

  return (
    <>
      {user ? (
        <AppOnboardingTour
          isOpen={isGuideActive}
          userId={user.id}
          onClose={() => setIsGuideActive(false)}
        />
      ) : null}

      <AppShell
        navItems={navItems}
        pathname={location.pathname}
        user={user}
        isLoggedIn={isLoggedIn}
        hideChrome={isDraftRoomPage}
        hideDecor={isCreateLeaguePage}
        hideFloatingActions={isDraftRoomPage || isCreateLeaguePage}
        compactContent={isDraftRoomPage || isCreateLeaguePage}
        onSignOut={logout}
        mainScrollRef={mainScrollRef}
      >
        {children}
      </AppShell>
    </>
  );
};

export default Layout;
