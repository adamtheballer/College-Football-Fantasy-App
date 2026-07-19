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

export const isDraftRoomRoute = (pathname: string) =>
  pathname === "/draft/mock/single-player" || /^\/league\/[^/]+\/draft$/.test(pathname);

export const isCreateLeagueRoute = (pathname: string) => pathname === "/leagues/create";

export const isAuthFlowRoute = (pathname: string) =>
  pathname === "/login" ||
  pathname === "/signup" ||
  pathname === "/reset-password";

export const getShellNavItems = (
  user: User | null,
  isLoggedIn: boolean,
  chatUnreadCount = 0,
): ShellNavItem[] => {
  if (!isLoggedIn) {
    return [
      { name: "HOME", path: "/", icon: Home },
      { name: "LEAGUES", path: "/leagues", icon: Trophy },
      { name: "SETTINGS", path: "/settings", icon: Settings },
      { name: "SIGN IN", path: "/login", icon: LogIn, kind: "auth" },
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
    { name: "INJURY CENTER", path: "/injury-center", icon: ShieldAlert },
    { name: "ALERTS", path: "/alerts", icon: Bell },
    { name: "MOCK DRAFT", path: "/draft", icon: Timer },
    ...(user?.isAdmin
      ? [{ name: "ADMIN SCORING", path: "/admin/scoring", icon: Wrench, kind: "admin" as const }]
      : []),
    { name: "SETTINGS", path: "/settings", icon: Settings },
    { name: "SIGN OUT", path: "#", icon: LogOut, kind: "danger" },
  ];
};

export const getMobileNavItems = (items: ShellNavItem[]) => {
  const preferred = new Set(["HOME", "LEAGUES", "CHATS", "MOCK DRAFT", "SETTINGS"]);
  const filtered = items.filter((item) => preferred.has(item.name));

  if (filtered.length >= 4) {
    return filtered.slice(0, 5);
  }

  return items.filter((item) => item.kind !== "danger" && item.kind !== "admin").slice(0, 5);
};

export const navDomId = (name: string) => `nav-${name.toLowerCase().replace(/\s+/g, "-")}`;
