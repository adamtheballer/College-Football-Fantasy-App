import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Capacitor } from "@capacitor/core";
import { focusManager } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import { resolveNotificationPath, type NotificationDestination } from "@/lib/notifications";
import { clearPendingPushTap, readPendingPushTap } from "@/lib/push-navigation";
import { useNotifications } from "@/hooks/use-notifications";
import { clearBrowserPushIdentity, syncBrowserPushIdentity, updatePhoneNotificationBadge } from "@/lib/push-notifications";

/** Native taps wait for restored authentication and always ask the server for a current destination. */
export function PushNotificationCoordinator() {
  const { user, isBootstrapping } = useAuth();
  const navigate = useNavigate();
  useEffect(() => { if (!isBootstrapping && !user) void clearBrowserPushIdentity(); }, [user?.id, isBootstrapping]);
  const notifications = useNotifications(Boolean(user) && !isBootstrapping);
  useEffect(() => { if (user && !isBootstrapping && notifications.data) void updatePhoneNotificationBadge(notifications.data.unread_count).catch(() => undefined); }, [notifications.data?.unread_count, user?.id, isBootstrapping]);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const update = () => setRevision((value) => value + 1);
    window.addEventListener("cffb-push-tap", update);
    const recheck = () => { if (document.visibilityState === "visible" && user && !isBootstrapping) void syncBrowserPushIdentity(user.id); update(); };
    document.addEventListener("visibilitychange", recheck);
    let dispose: (() => void) | undefined;
    let mounted = true;
    if (Capacitor.isNativePlatform()) {
      void import("@capacitor/app").then(async ({ App }) => {
        const handle = await App.addListener("appStateChange", ({ isActive }) => {
          // Reuse this single native lifecycle subscription for query refreshes.
          // WebView visibility alone does not reliably signal iPhone foreground.
          focusManager.setFocused(isActive);
          if (isActive) recheck();
        });
        dispose = () => { void handle.remove(); };
        if (!mounted) dispose();
      });
    }
    return () => { mounted = false; window.removeEventListener("cffb-push-tap", update); document.removeEventListener("visibilitychange", recheck); dispose?.(); };
  }, [user?.id, isBootstrapping]);
  useEffect(() => {
    if (isBootstrapping) return;
    const tap = readPendingPushTap();
    if (!tap) return;
    if (!user) { navigate("/login", { replace: true }); return; }
    if (tap.recipientId !== user.id) { clearPendingPushTap(); navigate("/alerts"); return; }
    let active = true;
    const controller = new AbortController();
    void apiGet<{ allowed: boolean; destination: NotificationDestination | null }>(`/notifications/events/${tap.eventId}/open`, undefined, controller.signal)
      .then((result) => {
        if (!active || readPendingPushTap()?.eventId !== tap.eventId) return;
        clearPendingPushTap();
        navigate(result.allowed ? resolveNotificationPath(result.destination) : "/alerts");
      }).catch(() => {
        if (!active) return;
        clearPendingPushTap();
        navigate("/alerts");
      });
    return () => { active = false; controller.abort(); };
  }, [user?.id, isBootstrapping, revision, navigate]);
  return null;
}
