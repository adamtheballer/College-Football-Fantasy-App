import React, {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation, useNavigate, useNavigationType } from "react-router-dom";

import { AppOnboardingTour } from "./AppOnboardingTour";
import { AppShell } from "./app-shell/AppShell";
import {
  getShellNavItems,
  isAuthFlowRoute,
  isCreateLeagueRoute,
  isDraftRoomRoute,
  isLeagueMatchupRoute,
  isSaturdayPick6Route,
} from "./app-shell/navigation";
import { useAuth } from "@/hooks/use-auth";
import { useChatUnreadSummary } from "@/hooks/use-chat";
import { useNotifications } from "@/hooks/use-notifications";
import { clearPendingGuide, shouldStartGuide } from "@/lib/onboarding";

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigationType = useNavigationType();
  const navigate = useNavigate();
  const { user, logout, isBootstrapping, isLoggedIn } = useAuth();
  // Wait for the refresh-cookie restore before fan-out requests. A cached
  // user alone is not proof that the short-lived access token is usable.
  const sessionReady = isLoggedIn && !isBootstrapping;
  const { data: unreadChatSummary } = useChatUnreadSummary(
    sessionReady,
    location.pathname === "/chats",
  );
  const { data: notifications } = useNotifications(sessionReady);
  const [isGuideActive, setIsGuideActive] = useState(false);
  const [guidedNavItem, setGuidedNavItem] = useState<string | undefined>();
  const mainScrollRef = useRef<HTMLElement | null>(null);
  const scrollPositionsRef = useRef(new Map<string, number>());

  const navItems = useMemo(
    () =>
      getShellNavItems(
        user,
        isLoggedIn,
        unreadChatSummary?.total_unread ?? 0,
        notifications?.unread_count ?? 0,
      ),
    [isLoggedIn, notifications?.unread_count, unreadChatSummary?.total_unread, user],
  );

  const isDraftRoomPage = isDraftRoomRoute(location.pathname);
  const isCreateLeaguePage = isCreateLeagueRoute(location.pathname);
  const isLeagueMatchupPage = isLeagueMatchupRoute(location.pathname);
  const isSaturdayPick6Page = isSaturdayPick6Route(location.pathname);
  const isAuthFlowPage = isAuthFlowRoute(location.pathname);
  const replayGuideRequested = Boolean(
    (location.state as { replayGuide?: boolean } | null)?.replayGuide,
  );

  // AppShell deliberately owns scrolling. New destinations start at the top,
  // while browser Back/Forward restores the manager's prior research position.
  // Keeping this per history entry avoids throwing a manager back to the top
  // after they inspect a player card or return from a league child route.
  useLayoutEffect(() => {
    const scroller = mainScrollRef.current;
    const targetTop = navigationType === "POP" ? scrollPositionsRef.current.get(location.key) ?? 0 : 0;
    scroller?.scrollTo({ top: targetTop, left: 0, behavior: "auto" });
    window.scrollTo({ top: targetTop, left: 0, behavior: "auto" });
    return () => {
      if (scroller) scrollPositionsRef.current.set(location.key, scroller.scrollTop);
    };
  }, [location.key, navigationType]);

  useEffect(() => {
    if (!user) {
      setIsGuideActive(false);
      setGuidedNavItem(undefined);
      return;
    }

    if (isAuthFlowPage) {
      setIsGuideActive(false);
      setGuidedNavItem(undefined);
      return;
    }

    const guideShouldStart = shouldStartGuide(user.id, replayGuideRequested);
    if (!guideShouldStart) {
      clearPendingGuide(user.id);
      setIsGuideActive(false);
      setGuidedNavItem(undefined);
      return;
    }

    if (location.pathname !== "/") {
      navigate("/", { replace: true, state: { replayGuide: replayGuideRequested } });
      return;
    }

    if (mainScrollRef.current) {
      mainScrollRef.current.scrollTo({ top: 0, left: 0, behavior: "auto" });
    } else {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
    clearPendingGuide(user.id);
    setIsGuideActive(true);
  }, [isAuthFlowPage, location.pathname, navigate, replayGuideRequested, user]);

  return (
    <>
      {user ? (
        <AppOnboardingTour
          isOpen={isGuideActive}
          userId={user.id}
          onStepChange={setGuidedNavItem}
          onClose={() => {
            setIsGuideActive(false);
            setGuidedNavItem(undefined);
          }}
        />
      ) : null}

      <AppShell
        navItems={navItems}
        pathname={location.pathname}
        user={user}
        isLoggedIn={isLoggedIn}
        hideChrome={isDraftRoomPage || isAuthFlowPage}
        hideFloatingActions={
          isLoggedIn ||
          isDraftRoomPage ||
          isCreateLeaguePage ||
          isSaturdayPick6Page ||
          isAuthFlowPage
        }
        compactContent={isDraftRoomPage || isCreateLeaguePage || isLeagueMatchupPage}
        // Draft rooms use the same page-level scroll owner as every other
        // route. A fixed outer viewport plus a nested player-board scroller
        // traps touch gestures and makes the board feel stuck on mobile.
        fixedViewport={false}
        onSignOut={logout}
        mainScrollRef={mainScrollRef}
        guidedNavItem={guidedNavItem}
      >
        {children}
      </AppShell>
    </>
  );
};

export default Layout;
