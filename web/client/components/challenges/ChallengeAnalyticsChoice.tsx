import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { apiGet, apiChallengeWrite } from "@/lib/api";
export function ChallengeAnalyticsChoice() {
  const { user } = useAuth();
  const cache = useQueryClient();
  const key = ["weekly-challenges", "analytics-preference", user?.id];
  const q = useQuery({
    queryKey: key,
    enabled: !!user,
    queryFn: () =>
      apiGet<{ enabled: boolean }>("/weekly-challenges/analytics-preference"),
  });
  const m = useMutation({
    mutationFn: (enabled: boolean) =>
      apiChallengeWrite<{ enabled: boolean }>(
        user!.id,
        "PUT",
        "/weekly-challenges/analytics-preference",
        { enabled },
      ),
    onSuccess: (data) => {
      cache.setQueryData(key, data);
      try {
        localStorage.setItem(
          `cffb_analytics_opt_out_${user!.id}`,
          String(!data.enabled),
        );
      } catch {
        /* The saved account preference is authoritative. */
      }
    },
  });
  return (
    <div className="border-t border-border pt-4 text-xs text-muted-foreground">
      <label className="flex min-h-11 items-center gap-3">
        <input
          type="checkbox"
          aria-label="Optional challenge analytics"
          disabled={!q.data || m.isPending}
          checked={q.data?.enabled ?? false}
          onChange={(e) => m.mutate(e.target.checked)}
        />
        Optional challenge views, share counts and creator referral analytics
      </label>
      <p>
        Saved to your account. Browser Do Not Track is respected. Entries and
        scores still operate when analytics are off.
      </p>
      {(q.isError || m.isError) && (
        <p role="alert">
          Could not load or save the analytics preference.{" "}
          <button className="underline" onClick={() => void q.refetch()}>
            Retry
          </button>
        </p>
      )}
    </div>
  );
}
