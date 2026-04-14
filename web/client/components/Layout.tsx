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
  Bell,
  BarChart3,
  MessageSquare,
  Bookmark,
  UserPlus,
  ShieldAlert,
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
        { name: "ROSTER", path: "/rosters", icon: ClipboardList },
        { name: "CHATS", path: "/chats", icon: MessageSquare },
        { name: "WATCHLIST", path: "/watchlists", icon: Bookmark },
        { name: "WAIVER WIRE", path: "/waivers", icon: UserPlus },
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
        { name: "SIGN IN", path: "/login", icon: LogIn },
      ];

  const isDraftPage = location.pathname.startsWith("/draft");

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
      <FloatingQuickActions />

      {/* Sidebar - Conditionally Hidden on Draft Page */}
      {!isDraftPage && (
        <aside className="w-72 h-screen sticky top-0 border-r border-border bg-sidebar-background/40 backdrop-blur-xl flex flex-col shrink-0 relative z-10 overflow-hidden">
          {/* Subtle Sidebar Left-side Shine */}
          <div className="absolute top-0 left-0 w-full h-[100%] bg-sky-500/5 rounded-full blur-[100px] -ml-24 pointer-events-none" />

          <div className="p-8 relative z-10">
            <h1 className="text-xl font-black tracking-tighter text-foreground uppercase italic bg-gradient-to-r from-primary to-blue-400 bg-clip-text text-transparent">
              CFB Fantasy
            </h1>
          </div>

          <nav className="flex-1 px-6 space-y-3 mt-4 pb-6 relative z-10 flex flex-col overflow-hidden">
            {sidebarItems.map((item) => {
              const isActive = location.pathname === item.path;
              const navId = `nav-${item.name.toLowerCase().replace(/\s+/g, "-")}`;
              const content = (
                <div
                  id={navId}
                  data-nav-item="true"
                  data-nav-active={isActive ? "true" : "false"}
                  className={cn(
                    "flex items-center gap-4 px-6 py-4 rounded-2xl text-[11px] font-black tracking-[0.1em] transition-all duration-300 uppercase relative overflow-hidden group w-full text-left",
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
                  <button key={item.name} onClick={item.onClick} className="w-full">
                    {content}
                  </button>
                );
              }

              return (
                <Link key={item.name} to={item.path}>
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
        {!isDraftPage && (
          <header id="app-header" className="border-b border-border bg-background/60 backdrop-blur-2xl sticky top-0 z-[120] flex flex-col px-12 py-6">
            <div className="flex items-center justify-between">
              <h2 className="text-[10px] font-black tracking-[0.3em] text-primary/80 uppercase">College Football Fantasy</h2>
              <div className="h-[1px] flex-1 mx-8 bg-gradient-to-r from-border/50 via-primary/20 to-border/50" />
              <div className="flex items-center gap-6">
                 {isLoggedIn ? (
                   <div className="flex items-center gap-3">
                      <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-40 italic">Dashboard</span>
                      <div className="w-1 h-1 rounded-full bg-border" />
                      <span className="text-[10px] font-black tracking-[0.2em] text-foreground uppercase animate-in fade-in slide-in-from-right-2 duration-700">
                        Welcome <span className="text-primary italic">{user?.firstName}</span>
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

        <div className={cn("flex-1", isDraftPage ? "p-0" : "p-8")}>
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
