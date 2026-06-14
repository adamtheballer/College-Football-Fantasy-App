import React, { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  Home,
  Trophy,
  Settings,
  LogIn,
  LogOut,
  ClipboardList,
  BarChart3,
  MessageSquare,
  Bookmark,
  UserPlus,
  ShieldAlert,
  ArrowRightLeft,
  Clock3,
} from "lucide-react";

import { BackgroundEffects } from "./BackgroundEffects";
import { useAuth } from "@/hooks/use-auth";
import { AppOnboardingTour } from "./AppOnboardingTour";
import { clearPendingGuide, hasPendingGuide } from "@/lib/onboarding";
import { FloatingQuickActions } from "./FloatingQuickActions";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useLeagueDetail } from "@/hooks/use-leagues";

interface LayoutProps {
  children: React.ReactNode;
}

type SidebarItem = {
  name: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick?: () => void;
};

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, isLoggedIn } = useAuth();
  const { activeLeagueId } = useActiveLeagueId();
  const { data: activeLeague } = useLeagueDetail(
    activeLeagueId ?? undefined,
    isLoggedIn && typeof activeLeagueId === "number"
  );
  const [isGuideActive, setIsGuideActive] = useState(false);
  const mainScrollRef = useRef<HTMLElement | null>(null);
  const isAuthScreen = location.pathname === "/login" || location.pathname === "/signup";

  const activeDraftStatus = activeLeague?.draft?.status ?? null;
  const shouldShowRealDraftTab = Boolean(
    activeLeagueId && activeDraftStatus && ["scheduled", "live", "paused"].includes(activeDraftStatus)
  );
  const realDraftPath =
    activeLeagueId && activeDraftStatus === "live"
      ? `/league/${activeLeagueId}/draft`
      : activeLeagueId
        ? `/league/${activeLeagueId}/lobby`
        : "/leagues";

  const loggedInSidebarItems: SidebarItem[] = [
        { name: "HOME", path: "/", icon: Home },
        { name: "LEAGUES", path: "/leagues", icon: Trophy },
        ...(shouldShowRealDraftTab ? [{ name: "DRAFT", path: realDraftPath, icon: Clock3 }] : []),
        { name: "ROSTER", path: "/rosters", icon: ClipboardList },
        { name: "CHATS", path: "/chats", icon: MessageSquare },
        { name: "WATCHLIST", path: "/watchlists", icon: Bookmark },
        { name: "WAIVER WIRE", path: "/waivers", icon: UserPlus },
        { name: "TRADES", path: "/trade", icon: ArrowRightLeft },
        { name: "INJURY CENTER", path: "/injury-center", icon: ShieldAlert },
        { name: "STATS", path: "/stats", icon: BarChart3 },
        { name: "SETTINGS", path: "/settings", icon: Settings },
        {
          name: "SIGN OUT",
          path: "#",
          icon: LogOut,
          onClick: logout,
        },
      ];

  const sidebarItems: SidebarItem[] = isLoggedIn
    ? loggedInSidebarItems
    : [
        { name: "HOME", path: "/", icon: Home },
        { name: "LEAGUES", path: "/leagues", icon: Trophy },
        { name: "STATS", path: "/stats", icon: BarChart3 },
        { name: "SIGN IN", path: "/login", icon: LogIn },
      ];

  const isFullScreenDraftRoom =
    /^\/leagues?\/[^/]+\/(lobby|draft)\/?$/.test(location.pathname) ||
    /^\/draft\/mock\/[^/]+\/(lobby|room)\/?$/.test(location.pathname) ||
    /^\/draft\/mock\/single\/[^/]+\/?$/.test(location.pathname) ||
    /^\/mock-drafts\/[^/]+\/(lobby|room|board)\/?$/.test(location.pathname);

  useEffect(() => {
    if (!user) {
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
  }, [location.pathname, navigate, user]);

  return (
    <div className="flex h-screen text-foreground font-sans selection:bg-primary/30 selection:text-primary relative overflow-hidden">
      {user && (
        <AppOnboardingTour
          isOpen={isGuideActive}
          userId={user.id}
          onClose={() => setIsGuideActive(false)}
        />
      )}

      {/* Reusable Dramatic Background Effects */}
      <BackgroundEffects />
      {!isFullScreenDraftRoom ? <FloatingQuickActions /> : null}

      {/* Sidebar - Conditionally Hidden in full-screen draft room */}
      {!isFullScreenDraftRoom && (
        <aside className="w-72 h-screen sticky top-0 bg-sidebar-background/55 backdrop-blur-xl flex flex-col shrink-0 relative z-10 overflow-hidden border-r border-cyan-200/10">
          {/* Subtle Sidebar Left-side Shine */}
          <div className="absolute top-0 left-0 w-full h-[100%] bg-sky-400/10 rounded-full blur-[100px] -ml-24 pointer-events-none" />
          <div className="absolute bottom-0 right-0 h-56 w-56 rounded-full bg-amber-300/10 blur-[90px] pointer-events-none" />

          <div className="p-8 relative z-10">
            <h1 className="text-xl font-black tracking-tighter text-foreground uppercase italic bg-gradient-to-r from-primary to-blue-400 bg-clip-text text-transparent">
              CFB Fantasy
            </h1>
          </div>

          <nav className="cfb-sidebar-nav flex-1 min-h-0 px-6 space-y-3 mt-4 pb-6 relative z-10 flex flex-col overflow-y-auto overscroll-contain">
            {sidebarItems.map((item) => {
              const isActive = location.pathname === item.path;
              const navId = `nav-${item.name.toLowerCase().replace(/\s+/g, "-")}`;
              const content = (
                <div
                  id={navId}
                  data-nav-item="true"
                  data-nav-active={isActive ? "true" : "false"}
                  className={cn(
                    "flex shrink-0 items-center gap-4 px-6 py-4 rounded-2xl text-[11px] font-black tracking-[0.1em] transition-all duration-300 uppercase relative overflow-hidden group w-full text-left",
                    isActive
                      ? "text-primary-foreground shadow-[0_0_26px_rgba(var(--primary),0.25)] border border-white/10 bg-gradient-to-r from-primary to-blue-500"
                      : "text-muted-foreground hover:text-primary-foreground hover:shadow-[0_0_22px_rgba(var(--primary),0.20)] hover:border hover:border-white/10 hover:bg-gradient-to-r hover:from-primary hover:to-blue-500"
                  )}
                >
                  <item.icon className={cn(
                    "w-4 h-4 transition-all duration-300",
                    isActive
                      ? "text-primary-foreground"
                      : "text-primary group-hover:text-primary-foreground group-hover:scale-110"
                  )} />
                  {item.name}
                  {isActive && (
                    <div className="nav-active-overlay absolute inset-0 bg-gradient-to-r from-white/10 to-transparent pointer-events-none" />
                  )}
                </div>
              );

              if (item.onClick) {
                return (
                  <button key={item.name} onClick={item.onClick} className="w-full shrink-0">
                    {content}
                  </button>
                );
              }

              return (
                <Link key={item.name} to={item.path} className="shrink-0">
                  {content}
                </Link>
              );
            })}
          </nav>
        </aside>
      )}

      {/* Main Content */}
      <main ref={mainScrollRef} data-app-scroll="true" className="flex-1 h-screen flex flex-col min-w-0 overflow-y-auto relative">
        {/* Top Header - Conditionally hidden in full-screen draft room */}
        {!isFullScreenDraftRoom && (
          <header id="app-header" className="bg-background/65 backdrop-blur-2xl sticky top-0 z-[120] flex flex-col px-12 py-6 border-b border-cyan-200/10">
            <div className="flex items-center justify-between">
              <h2 className="text-[10px] font-black tracking-[0.3em] text-primary/80 uppercase">College Football Fantasy</h2>
              <div className="h-[1px] flex-1 mx-8 opacity-0" />
              <div className="flex min-w-fit items-center gap-6 overflow-visible">
                 {isLoggedIn ? (
                   <div className="flex min-w-fit items-center gap-3 overflow-visible">
                      <span className="whitespace-nowrap text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground opacity-40 italic">Dashboard</span>
                      <div className="w-1 h-1 rounded-full bg-border" />
                      <span className="whitespace-nowrap py-1 pr-2 text-[10px] font-black uppercase leading-none tracking-[0.2em] text-foreground animate-in fade-in slide-in-from-right-2 duration-700">
                        Welcome <span className="inline-block pr-1 text-primary italic">{user?.firstName}</span>
                      </span>
                   </div>
                 ) : (
                   <div className="flex items-center gap-3">
                      <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/40 uppercase tracking-widest">Guest Access</span>
                   </div>
                 )}
              </div>
            </div>
          </header>
        )}

        <div className={cn("flex-1", isFullScreenDraftRoom ? "p-0" : "p-8")}>
          {!isFullScreenDraftRoom ? (
            <div className="pointer-events-none absolute inset-x-0 top-0 h-48 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.08),transparent_55%)]" />
          ) : null}
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
