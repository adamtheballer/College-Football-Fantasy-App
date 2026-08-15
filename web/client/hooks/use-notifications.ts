import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPatch, apiPost } from "@/lib/api";
import type { NotificationAlert, NotificationList } from "@/lib/notifications";

export const notificationQueryKey = ["notifications", "alerts"] as const;

export const useNotifications = (enabled: boolean) =>
  useQuery({
    queryKey: notificationQueryKey,
    enabled,
    queryFn: () => apiGet<NotificationList>("/notifications/alerts", { limit: 50 }),
    refetchInterval: enabled ? 30_000 : false,
  });

export const useMarkNotificationRead = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, read }: { id: number; read: boolean }) =>
      apiPatch<NotificationAlert>(`/notifications/alerts/${id}`, { read }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationQueryKey }),
  });
};

export const useMarkAllNotificationsRead = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<{ updated: number }>("/notifications/alerts/read-all", {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationQueryKey }),
  });
};
