import type { ComponentType } from "react";
import {
  Bell,
  Home,
  LogIn,
  LogOut,
  MessageSquare,
  Settings,
  ShieldAlert,
  Timer,
  Trophy,
  Wrench,
} from "lucide-react";

import type { User } from "@/hooks/use-auth";

export type ShellNavItem = {
  name: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
  kind?: "primary" | "auth" | "danger" | "admin";
  badge?: string;
};

export const isShellNavItemActive = (pathname: string, item: Pick<ShellNavItem, "path">) =>
  item.path === "/"
    ? pathname === "/"
    : item.path === "/leagues"
      ? pathname === "/leagues" || pathname.startsWith("/leagues/") || pathname.startsWith("/league/")
    : pathname === item.path || pathname.startsWith(`${item.path}/`);

export const isDraftRoomRoute = (pathname: string) =>
  pathname === "/draft/mock/single-player" || /^\/labs\/dynasty\/[^/]+\/draft$/.test(pathname) || /^\/league\/[^/]+\/draft$/.test(pathname);

export const isCreateLeagueRoute = (pathname: string) => pathname === "/leagues/create";

// All six league sections share one header/rail and shell inset. Draft/lobby
// routes keep their existing, separate layout.
export const isLeagueSectionRoute = (pathname: string) =>
  /^\/league\/[1-9]\d*(?:\/(?:roster|matchup|waivers|watchlist|chat|settings))?\/?$/.test(pathname);

export const isLeagueMatchupRoute = (pathname: string) =>
  /^\/league\/[^/]+\/matchup\/?$/.test(pathname);

export const isSaturdayPick6Route = (pathname: string) => pathname === "/saturday-pick-6";

export const isAuthFlowRoute = (pathname: string) =>
  pathname === "/login" ||
  pathname === "/signup" ||
  pathname === "/reset-password" ||
  pathname === "/forgot-password";

export const getShellNavItems = (
  user: User | null,
  isLoggedIn: boolean,
  chatUnreadCount = 0,
  notificationUnreadCount = 0,
): ShellNavItem[] => {
  if (!isLoggedIn) {
    return [
      { name: "SIGN IN", path: "/login", icon: LogIn, kind: "auth" },
      { name: "LEAGUES", path: "/leagues", icon: Trophy },
      { name: "SETTINGS", path: "/settings", icon: Settings },
    ];
  }

  return [
    { name: "HOME", path: "/", icon: Home },
    { name: "LEAGUES", path: "/leagues", icon: Trophy },
    {
      name: "CHATS",
      path: "/chats",
      icon: MessageSquare,
      badge: chatUnreadCount > 99 ? "99+" : chatUnreadCount > 0 ? String(chatUnreadCount) : undefined,
    },
    { name: "MOCK DRAFT", path: "/draft", icon: Timer },
    { name: "CHALLENGES", path: "/weekly-challenges", icon: Trophy },
    { name: "INJURY CENTER", path: "/injury-center", icon: ShieldAlert },
    {
      name: "ALERTS",
      path: "/alerts",
      icon: Bell,
      badge: notificationUnreadCount > 99 ? "99+" : notificationUnreadCount > 0 ? String(notificationUnreadCount) : undefined,
    },
    ...(user?.isAdmin
      ? [
          { name: "ADMIN SCORING", path: "/admin/scoring", icon: Wrench, kind: "admin" as const },
          { name: "ADMIN SCHEDULES", path: "/admin/schedules", icon: Wrench, kind: "admin" as const },
        ]
      : []),
    { name: "SETTINGS", path: "/settings", icon: Settings },
    { name: "SIGN OUT", path: "#", icon: LogOut, kind: "danger" },
  ];
};

export const getMobileNavItems = (items: ShellNavItem[]) => {
  // Keep all five primary destinations plus More visible on signed-in phones.
  const preferred = ["HOME", "LEAGUES", "CHATS", "MOCK DRAFT", "CHALLENGES"];
  const byName = new Map(items.map((item) => [item.name, item]));
  const filtered = preferred.flatMap((name) => {
    const item = byName.get(name);
    return item ? [item] : [];
  });

  if (filtered.length >= 3) return filtered;

  return items.filter((item) => item.kind !== "danger" && item.kind !== "admin").slice(0, 4);
};

export const navDomId = (name: string) => `nav-${name.toLowerCase().replace(/\s+/g, "-")}`;
