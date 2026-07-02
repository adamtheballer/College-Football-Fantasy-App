import React, { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  Home,
  Trophy,
  Settings,
  LogIn,
  LogOut,
  Bell,
  BarChart3,
  MessageSquare,
  ShieldAlert,
  Timer,
} from "lucide-react";

import { BackgroundEffects } from "./BackgroundEffects";
import { useAuth } from "@/hooks/use-auth";
import { AppOnboardingTour } from "./AppOnboardingTour";
import { clearPendingGuide, hasPendingGuide } from "@/lib/onboarding";
import { FloatingQuickActions } from "./FloatingQuickActions";

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
  const [isGuideActive, setIsGuideActive] = useState(false);
  const mainScrollRef = useRef<HTMLElement | null>(null);

  const sidebarItems: SidebarItem[] = isLoggedIn
    ? [
        { name: "HOME", path: "/", icon: Home },
        { name: "LEAGUES", path: "/leagues", icon: Trophy },
        { name: "DRAFT", path: "/draft", icon: Timer },
        { name: "CHATS", path: "/chats", icon: MessageSquare },
        { name: "INJURY CENTER", path: "/injury-center", icon: ShieldAlert },
        { name: "ALERTS", path: "/alerts", icon: Bell },
        { name: "STATS", path: "/stats", icon: BarChart3 },
        { name: "SETTINGS", path: "/settings", icon: Settings },
        {
          name: "SIGN OUT",
          path: "#",
          icon: LogOut,
          onClick: logout,
        },
      ]
    : [
        { name: "HOME", path: "/", icon: Home },
        { name: "LEAGUES", path: "/leagues", icon: Trophy },
        { name: "STATS", path: "/stats", icon: BarChart3 },
        { name: "SETTINGS", path: "/settings", icon: Settings },
        { name: "SIGN IN", path: "/login", icon: LogIn },
      ];

  const isDraftRoomPage =
    location.pathname === "/draft/mock/single-player" ||
    /^\/league\/[^/]+\/draft$/.test(location.pathname);
  const isCreateLeaguePage = location.pathname === "/leagues/create";

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

      {!isCreateLeaguePage && <BackgroundEffects />}
      {!isDraftRoomPage && !isCreateLeaguePage && <FloatingQuickActions />}

      {/* Sidebar - hidden only inside active draft rooms */}
      {!isDraftRoomPage && (
        <aside className="w-72 h-screen sticky top-0 border-r border-sky-200/15 bg-[#050b16] flex flex-col shrink-0 relative z-10 overflow-hidden shadow-[inset_-1px_0_0_rgba(125,211,252,0.16),22px_0_90px_rgba(14,165,233,0.10)]">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_9%,rgba(56,189,248,0.18),transparent_34%),radial-gradient(circle_at_85%_72%,rgba(59,130,246,0.10),transparent_36%),linear-gradient(180deg,rgba(8,47,73,0.24),transparent_48%)]" />
          <div className="pointer-events-none absolute inset-y-8 right-0 w-px bg-gradient-to-b from-transparent via-sky-200/35 to-transparent" />
          <div className="p-8 relative z-10">
            <h1 className="font-sans text-[1.75rem] font-black tracking-[-0.08em] text-[#F8FAFC] uppercase italic drop-shadow-[0_0_22px_rgba(125,211,252,0.20)]">
              CFB Fantasy
            </h1>
          </div>

          <nav className="flex-1 px-5 pb-8 pt-3 relative z-10 flex flex-col justify-between overflow-hidden">
            {sidebarItems.map((item) => {
              const isActive = location.pathname === item.path;
              const isGuestSignIn = !isLoggedIn && item.name === "SIGN IN";
              const isSignOut = item.name === "SIGN OUT";
              const navId = `nav-${item.name.toLowerCase().replace(/\s+/g, "-")}`;
              const content = (
                <div
                  id={navId}
                  data-nav-item="true"
                  data-nav-active={isActive ? "true" : "false"}
                  className={cn(
                    "flex min-h-[58px] items-center gap-4 px-4 py-3 rounded-2xl border font-sans text-[13px] font-extrabold uppercase tracking-[0.08em] transition-all duration-300 relative group w-full text-left",
                    isSignOut
                      ? "border-transparent text-red-300/45 hover:-scale-x-100 hover:border-red-400/45 hover:bg-red-500/15 hover:text-red-100 hover:shadow-[0_0_36px_rgba(239,68,68,0.24)]"
                      : isGuestSignIn
                      ? "border-sky-200/45 bg-[linear-gradient(135deg,rgba(125,211,252,0.28),rgba(59,130,246,0.22))] text-white shadow-[0_0_0_1px_rgba(125,211,252,0.16),0_0_38px_rgba(56,189,248,0.28)] hover:border-sky-100/70 hover:brightness-110"
                      : isActive
                      ? "border-sky-300/45 bg-[linear-gradient(135deg,rgba(56,189,248,0.18),rgba(59,130,246,0.10))] text-white shadow-[0_0_0_1px_rgba(125,211,252,0.12),0_0_32px_rgba(56,189,248,0.20)]"
                      : "border-transparent text-[#9AA8BC] hover:border-sky-300/18 hover:bg-sky-300/[0.06] hover:text-[#F8FAFC]"
                  )}
                >
                  <item.icon className={cn(
                    "w-4 h-4 transition-colors duration-300",
                    isSignOut
                      ? "text-red-300/45 group-hover:text-red-100"
                      : isGuestSignIn
                      ? "text-[#BAE6FD]"
                      : isActive
                      ? "text-[#7DD3FC]"
                      : "text-[#64748B] group-hover:text-[#F8FAFC]"
                  )} />
                  <span className={isSignOut ? "transition-transform duration-300 group-hover:-scale-x-100" : undefined}>
                    {item.name}
                  </span>
                  {isActive && !isSignOut && (
                    <div className="nav-active-overlay pointer-events-none absolute inset-0 rounded-xl bg-[radial-gradient(circle_at_22%_50%,rgba(125,211,252,0.18),transparent_58%)]" />
                  )}
                </div>
              );

              if (item.onClick) {
                return (
                  <button key={item.name} onClick={item.onClick} className="w-full">
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
      )}

      {/* Main Content */}
      <main ref={mainScrollRef} data-app-scroll="true" className="flex-1 h-screen flex flex-col min-w-0 overflow-y-auto relative">
        {/* Top Header - Also Conditionally Hidden or Adjusted on Draft Page */}
        {!isDraftRoomPage && (
          <header id="app-header" className="border-b border-white/[0.08] bg-[#080C14]/95 backdrop-blur sticky top-0 z-[120] flex flex-col px-8 py-5">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold tracking-[0.08em] text-[#94A3B8] uppercase">College Football Fantasy</h2>
              <div className="h-px flex-1 mx-8 bg-white/[0.08]" />
              <div className="flex items-center gap-6">
                 {isLoggedIn ? (
                   <div className="flex items-center gap-3">
                      <span className="text-xs font-semibold tracking-[0.06em] text-[#64748B] uppercase">Dashboard</span>
                      <div className="w-1 h-1 rounded-full bg-white/20" />
                      <span className="text-xs font-semibold tracking-[0.06em] text-[#F8FAFC] uppercase animate-in fade-in slide-in-from-right-2 duration-700">
                        Welcome <span className="text-[#7DD3FC]">{user?.firstName}</span>
                      </span>
                   </div>
                 ) : (
                   <div className="flex items-center gap-3">
                      <span className="hidden text-xs font-semibold tracking-[0.08em] text-[#64748B] uppercase sm:inline">Guest Access</span>
                      <Link
                        to="/login"
                        className="inline-flex items-center gap-2 rounded-full border border-sky-200/35 bg-[linear-gradient(135deg,rgba(125,211,252,0.22),rgba(59,130,246,0.18))] px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-sky-50 shadow-[0_0_28px_rgba(56,189,248,0.18)] transition hover:border-sky-100/60 hover:bg-sky-300/20"
                      >
                        <LogIn className="h-3.5 w-3.5" />
                        Sign In
                      </Link>
                   </div>
                 )}
              </div>
            </div>
          </header>
        )}

        <div className={cn("flex-1", isDraftRoomPage || isCreateLeaguePage ? "p-0" : "p-8")}>
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
