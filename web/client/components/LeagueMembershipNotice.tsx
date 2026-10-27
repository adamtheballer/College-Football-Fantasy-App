import { Link, useLocation } from "react-router-dom";
import { useMembership } from "@/hooks/use-membership";

export function LeagueMembershipNotice() {
  const { data } = useMembership();
  const { pathname } = useLocation();
  const leagueId = Number(pathname.match(/^\/leagues\/(\d+)/)?.[1]);
  const league = data?.free_leagues.find((item) => item.id === leagueId);
  if (!data?.enforcement_active || data.active || !league || league.selected)
    return null;
  return (
    <aside className="cfb-panel mb-4 p-4" role="status">
      This league is read-only on your free plan.{" "}
      <Link className="underline" to="/membership">
        Choose two free leagues or upgrade to Pro.
      </Link>{" "}
      Your roster and history are preserved.
    </aside>
  );
}
