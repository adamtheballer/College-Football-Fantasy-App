import type { ComponentType } from "react";
import {
  Bell,
  Bug,
  Home,
  LogIn,
  LogOut,
  MessageSquare,
  Settings,
  ShieldAlert,
  Sparkles,
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

export const isSaturdayPick6Route = (pathname: string) => pathname === "/saturday-pick-6";

export const isAuthFlowRoute = (pathname: string) =>
  pathname === "/login" ||
  pathname === "/signup" ||
  pathname === "/reset-password";

export const getShellNavItems = (
  user: User | null,
  isLoggedIn: boolean,
  chatUnreadCount = 0,
  supportAvailable = false,
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
    // This mailto workflow is only reachable after the server has supplied a
    // configured support address. Beta must not expose a dead feedback link.
    ...(supportAvailable ? [{ name: "REPORT BUG", path: "/report-bug", icon: Bug }] : []),
    { name: "COMING SOON", path: "/coming-soon", icon: Sparkles },
    { name: "MOCK DRAFT", path: "/draft", icon: Timer },
    ...(user?.isAdmin
      ? [{ name: "ADMIN SCORING", path: "/admin/scoring", icon: Wrench, kind: "admin" as const }]
      : []),
    { name: "SETTINGS", path: "/settings", icon: Settings },
    { name: "SIGN OUT", path: "#", icon: LogOut, kind: "danger" },
  ];
};

export const getMobileNavItems = (items: ShellNavItem[]) => {
  // Saturday Pick 6 remains a featured dashboard experience, not a permanent
  // mobile destination. Keep the available support route in the five-item bar.
  const preferred = ["HOME", "LEAGUES", "CHATS", "MOCK DRAFT", "REPORT BUG"];
  const byName = new Map(items.map((item) => [item.name, item]));
  const filtered = preferred.flatMap((name) => {
    const item = byName.get(name);
    return item ? [item] : [];
  });

  if (filtered.length >= 4) return filtered;

  return items.filter((item) => item.kind !== "danger" && item.kind !== "admin").slice(0, 5);
};

export const navDomId = (name: string) => `nav-${name.toLowerCase().replace(/\s+/g, "-")}`;
