import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import { SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
type Action = {
  key: string;
  title: string;
  detail: string;
  href: string;
  deadline: string | null;
};
export function HomeActions() {
  const { user, isBootstrapping } = useAuth();
  const q = useQuery({
    queryKey: ["home-actions", user?.id],
    enabled: !!user && !isBootstrapping,
    queryFn: () =>
      apiGet<{ data: Action[]; checked_at: string }>("/product/home-actions"),
    staleTime: 30_000,
  });
  if (q.isLoading)
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Checking your next moves…
      </p>
    );
  if (q.isError)
    return (
      <SurfaceCard>
        <p role="alert">Lineup and trade reminders could not load.</p>
        <Button variant="outline" onClick={() => void q.refetch()}>
          Retry reminders
        </Button>
      </SurfaceCard>
    );
  if (!q.data?.data.length)
    return (
      <p className="text-xs text-muted-foreground">
        No urgent lineup or trade actions right now.
      </p>
    );
  return (
    <section aria-label="Your next moves" className="space-y-3">
      <h2 className="cfb-section-title text-2xl">Your next moves</h2>
      <SurfaceCard padding="none">
        <ul className="divide-y divide-border">
          {q.data.data.map((a) => (
            <li key={a.key}>
              <Link
                className="block min-h-14 p-4 hover:bg-primary/5"
                to={a.href}
              >
                <p className="font-bold text-primary">{a.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {a.detail}
                  {a.deadline
                    ? ` · ${new Date(a.deadline).toLocaleString()}`
                    : ""}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      </SurfaceCard>
    </section>
  );
}
