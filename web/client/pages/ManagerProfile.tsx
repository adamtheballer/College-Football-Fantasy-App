import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import { type Participant } from "@/hooks/use-weekly-challenges";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { Button } from "@/components/ui/button";
export default function ManagerProfile() {
  const { userId } = useParams();
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["weekly-challenges", "profile", user?.id, userId],
    queryFn: () =>
      apiGet<Participant & { recognition: string[] }>(
        `/weekly-challenges/participants/${userId}`,
      ),
    enabled: !!user && Number(userId) > 0,
  });
  return (
    <div className="mx-auto max-w-2xl space-y-5 pb-24 pt-3">
      <Button asChild variant="outline">
        <Link to="/weekly-challenges/leaderboard">Leaderboard</Link>
      </Button>
      {query.isPending && <p role="status">Loading manager…</p>}
      {query.isError && <p role="alert">Manager profile unavailable.</p>}
      {query.data && (
        <>
          <div className="flex items-center gap-4">
            <ManagerAvatar
              managerName={query.data.display_name}
              avatarUrl={query.data.avatar_url}
            />
            <PageHeader
              title={query.data.display_name}
              eyebrow={
                query.data.username ? `@${query.data.username}` : "CFFB manager"
              }
            />
          </div>
          <SurfaceCard>
            <h2 className="cfb-section-title mb-3">Challenge Recognition</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Cosmetic achievements only. No cash, transferable, or redeemable
              value.
            </p>
            {query.data.recognition.length ? (
              <ul className="space-y-2">
                {query.data.recognition.map((label, i) => (
                  <li
                    className="rounded border border-primary/30 p-3 text-sm font-bold"
                    key={i}
                  >
                    {label}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm">No finalized badges yet.</p>
            )}
          </SurfaceCard>
        </>
      )}
    </div>
  );
}
