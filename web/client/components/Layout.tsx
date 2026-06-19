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
      {!isDraftPage && !isCreateLeaguePage && <FloatingQuickActions />}

      {/* Sidebar - Conditionally Hidden on Draft Page */}
      {!isDraftPage && (
        <aside className="cfb-sidebar-type w-72 h-screen sticky top-0 border-r border-white/[0.08] bg-[#080C14] flex flex-col shrink-0 relative z-10 overflow-hidden">
          <div className="p-8 relative z-10">
            <h1 className="text-[1.65rem] font-bold tracking-[-0.055em] text-[#F8FAFC] uppercase italic">
              CFB Fantasy
            </h1>
          </div>

          <nav className="flex-1 px-5 space-y-2 mt-4 pb-6 relative z-10 flex flex-col overflow-hidden">
            {sidebarItems.map((item) => {
              const isActive = location.pathname === item.path;
              const navId = `nav-${item.name.toLowerCase().replace(/\s+/g, "-")}`;
              const content = (
                <div
                  id={navId}
                  data-nav-item="true"
                  data-nav-active={isActive ? "true" : "false"}
                  className={cn(
                    "flex items-center gap-4 px-4 py-3.5 rounded-lg text-[17px] font-bold tracking-[0.035em] transition-colors duration-200 relative group w-full text-left",
                    isActive
                      ? "border-l-2 border-[#22C55E] bg-[#22C55E]/[0.12] text-white"
                      : "text-[#94A3B8] hover:bg-white/[0.05] hover:text-[#F8FAFC]"
                  )}
                >
                  <item.icon className={cn(
                    "w-4 h-4 transition-colors duration-200",
                    isActive
                      ? "text-[#22C55E]"
                      : "text-[#64748B] group-hover:text-[#F8FAFC]"
                  )} />
                  {item.name}
                  {isActive && (
                    <div className="nav-active-overlay absolute inset-y-2 left-0 w-0.5 rounded-full bg-[#22C55E] pointer-events-none" />
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
                        Welcome <span className="text-[#22C55E]">{user?.firstName}</span>
                      </span>
                   </div>
                 ) : (
                   <div className="flex items-center gap-3">
                      <span className="text-xs font-semibold tracking-[0.08em] text-[#64748B] uppercase">Guest Access</span>
                   </div>
                 )}
              </div>
            </div>
          </header>
        )}

        <div className={cn("flex-1", isDraftPage || isCreateLeaguePage ? "p-0" : "p-8")}>
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
