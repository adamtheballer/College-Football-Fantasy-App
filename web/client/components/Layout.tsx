import React, {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";

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
import { useRuntimeCapabilities } from "@/components/RuntimeCompatibilityGate";

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, isLoggedIn } = useAuth();
  const { support_email: supportEmail } = useRuntimeCapabilities();
  const { data: unreadChatSummary } = useChatUnreadSummary(
    isLoggedIn,
    location.pathname === "/chats",
  );
  const { data: notifications } = useNotifications(isLoggedIn);
  const [isGuideActive, setIsGuideActive] = useState(false);
  const mainScrollRef = useRef<HTMLElement | null>(null);

  const navItems = useMemo(
    () =>
      getShellNavItems(
        user,
        isLoggedIn,
        unreadChatSummary?.total_unread ?? 0,
        Boolean(supportEmail),
        notifications?.unread_count ?? 0,
      ),
    [isLoggedIn, notifications?.unread_count, supportEmail, unreadChatSummary?.total_unread, user],
  );

  const isDraftRoomPage = isDraftRoomRoute(location.pathname);
  const isCreateLeaguePage = isCreateLeagueRoute(location.pathname);
  const isLeagueMatchupPage = isLeagueMatchupRoute(location.pathname);
  const isSaturdayPick6Page = isSaturdayPick6Route(location.pathname);
  const isAuthFlowPage = isAuthFlowRoute(location.pathname);
  const replayGuideRequested = Boolean(
    (location.state as { replayGuide?: boolean } | null)?.replayGuide,
  );

  // AppShell deliberately owns scrolling so persistent navigation never creates
  // a second document scroller. Reset that one owner before a new route paints;
  // otherwise navigating from a long page can leave the next page at its old
  // bottom offset on mobile Safari.
  useLayoutEffect(() => {
    mainScrollRef.current?.scrollTo({ top: 0, left: 0, behavior: "auto" });
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [location.key, location.pathname, location.search]);

  useEffect(() => {
    if (!user) {
      setIsGuideActive(false);
      return;
    }

    if (isAuthFlowPage) {
      setIsGuideActive(false);
      return;
    }

    const guideShouldStart = shouldStartGuide(user.id, replayGuideRequested);
    if (!guideShouldStart) {
      clearPendingGuide(user.id);
      setIsGuideActive(false);
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
          onClose={() => setIsGuideActive(false)}
        />
      ) : null}

      <AppShell
        navItems={navItems}
        pathname={location.pathname}
        user={user}
        isLoggedIn={isLoggedIn}
        hideChrome={isDraftRoomPage}
        hideFloatingActions={
          isLoggedIn ||
          isDraftRoomPage ||
          isCreateLeaguePage ||
          isSaturdayPick6Page
        }
        compactContent={isDraftRoomPage || isCreateLeaguePage || isLeagueMatchupPage}
        // Draft rooms use the same page-level scroll owner as every other
        // route. A fixed outer viewport plus a nested player-board scroller
        // traps touch gestures and makes the board feel stuck on mobile.
        fixedViewport={false}
        onSignOut={logout}
        mainScrollRef={mainScrollRef}
      >
        {children}
      </AppShell>
    </>
  );
};

export default Layout;
