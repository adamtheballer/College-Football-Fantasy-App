import { Link } from "react-router-dom";
import { useMembership } from "@/hooks/use-membership";
import { Button } from "./ui/button";

export function MembershipGate({
  feature,
  children,
}: {
  feature: "weekly_challenges" | "dynasty";
  children: React.ReactNode;
}) {
  const membership = useMembership();
  if (
    !membership.enabled ||
    (membership.data &&
      (!membership.data.enforcement_active ||
        membership.data.features[feature]))
  )
    return <>{children}</>;
  if (membership.loading) return <p role="status">Checking membership…</p>;
  if (membership.error)
    return (
      <div role="alert">
        <p>Membership could not be verified. {membership.error.message}</p>
        <Button onClick={() => membership.refresh()}>Retry membership</Button>
      </div>
    );
  return (
    <section className="cfb-panel space-y-3 p-5">
      <h2 className="cfb-section-title">Pro membership required</h2>
      <p>
        {feature === "dynasty"
          ? "Dynasty participation"
          : "Weekly challenge entries"}{" "}
        is included with Pro for $10 USD per year.
      </p>
      <Button asChild>
        <Link to="/membership">View Pro membership</Link>
      </Button>
    </section>
  );
}
