import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useMembership } from "@/hooks/use-membership";
import { membershipApi } from "@/lib/membership";
import { isNativeMembership, nativeMembership } from "@/lib/native-membership";
import { Button } from "@/components/ui/button";

export default function MembershipPage() {
  const membership = useMembership();
  const [params] = useSearchParams();
  const native = isNativeMembership();
  const [product, setProduct] = useState<{
    displayPrice: string;
    displayName: string;
  } | null>(null);
  const [productError, setProductError] = useState("");
  const [notice, setNotice] = useState("");
  const [freeIds, setFreeIds] = useState<number[]>([]);
  const data = membership.data;
  useEffect(() => {
    setFreeIds(
      data?.free_leagues
        .filter((league) => league.selected)
        .map((league) => league.id) ?? [],
    );
  }, [data]);
  const selection = useMutation({
    retry: false,
    mutationFn: () => membershipApi.chooseFreeLeagues(freeIds),
    onSuccess: async () => {
      await membership.refresh();
      setNotice("Your two free leagues are saved for this season.");
    },
  });
  useEffect(() => {
    let disposed = false;
    if (native && data?.apple_purchase_ready && data.apple_product_id) {
      void nativeMembership
        .product({ productId: data.apple_product_id })
        .then((result) => {
          if (!disposed) {
            setProduct(result);
            setProductError("");
          }
        })
        .catch(() => {
          if (!disposed)
            setProductError(
              "The App Store price is unavailable. Try again later.",
            );
        });
    }
    return () => {
      disposed = true;
    };
  }, [native, data?.apple_purchase_ready, data?.apple_product_id]);
  useEffect(() => {
    if (!native && params.get("checkout") === "complete") {
      // The URL is only a hint to reconcile; it never changes the displayed plan.
      void membershipApi
        .sync()
        .then(() => membership.refresh())
        .catch(() =>
          setNotice(
            "Payment confirmation is pending. Refresh membership shortly.",
          ),
        );
    }
  }, [params, native]);
  const action = useMutation({
    retry: false,
    mutationFn: async (
      kind: "buy" | "manageWeb" | "manageApple" | "restore" | "refresh",
    ) => {
      setNotice("");
      if (kind === "refresh") {
        if (!native && data?.has_stripe_customer) await membershipApi.sync();
        await membership.refresh();
        return;
      }
      if (kind === "manageApple") {
        await nativeMembership.manage();
        return;
      }
      if (kind === "manageWeb") {
        window.location.assign((await membershipApi.portal()).url);
        return;
      }
      if (kind === "buy" && !native) {
        window.location.assign((await membershipApi.checkout()).url);
        return;
      }
      if (!data?.apple_product_id || !data.apple_account_token)
        throw new Error("App Store membership is unavailable.");
      if (kind === "restore") {
        const result = await nativeMembership.restore({
          productId: data.apple_product_id,
          appAccountToken: data.apple_account_token,
          synchronize: true,
        });
        if (!result.transactions.length) {
          setNotice(
            "No matching App Store purchases were found for this app account.",
          );
          return;
        }
        for (const tx of result.transactions) {
          await membershipApi.verifyApple(tx.signedTransaction);
          await nativeMembership.finish({ transactionId: tx.transactionId });
        }
        await membership.refresh();
        setNotice("Purchases verified. Your current plan is shown above.");
        return;
      }
      const result = await nativeMembership.purchase({
        productId: data.apple_product_id,
        appAccountToken: data.apple_account_token,
      });
      if (result.status === "cancelled") {
        setNotice("Purchase cancelled. Your plan is unchanged.");
        return;
      }
      if (result.status === "pending") {
        setNotice(
          "Purchase is pending App Store approval. Access activates after verification.",
        );
        return;
      }
      if (!result.transaction)
        throw new Error("The App Store did not return a verifiable purchase.");
      const verified = await membershipApi.verifyApple(
        result.transaction.signedTransaction,
      );
      await nativeMembership.finish({
        transactionId: result.transaction.transactionId,
      });
      await membership.refresh();
      setNotice(
        verified.active
          ? "Your Pro membership is active."
          : "Purchase verified; no current paid period is active. Check your membership dates.",
      );
    },
  });
  if (membership.loading) return <p role="status">Loading membership…</p>;
  if (membership.error)
    return (
      <div role="alert">
        <p>{membership.error.message}</p>
        <Button onClick={() => membership.refresh()}>Retry</Button>
      </div>
    );
  if (!data) return <p>Membership is unavailable.</p>;
  const ready = native
    ? data.apple_purchase_ready && !!product
    : data.web_checkout_ready;
  return (
    <main className="mx-auto max-w-4xl space-y-6 py-6">
      <header>
        <p className="cfb-micro-label">CFFB Pro</p>
        <h1 className="cfb-display-title">More ways to compete.</h1>
        <p>
          {native && product
            ? `${product.displayPrice} per year`
            : "$10 USD per year"}
        </p>
      </header>
      {!data.enforcement_active && (
        <p className="cfb-panel p-4">
          Membership starts with the 2027 season
          {data.launch_at
            ? ` (${new Date(data.launch_at).toLocaleDateString()})`
            : ""}
          . Current-season access stays unchanged. Purchases are not open yet.
        </p>
      )}
      <section className="cfb-panel space-y-3 p-5">
        <h2 className="cfb-section-title">
          Your plan: {data.active ? "Pro" : "Free"}
        </h2>
        <p>
          {data.league_count} league memberships
          {data.league_limit !== null ? ` / ${data.league_limit} included` : ""}
        </p>
        {data.expires_at && (
          <p>
            {data.cancel_at_period_end
              ? "Access ends"
              : "Current access through"}{" "}
            {new Date(data.expires_at).toLocaleDateString()}
          </p>
        )}
        {data.source === "early_access" && (
          <p>
            Your first Pro year is included with early access. No payment is
            required.
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          {!data.active && (
            <Button
              disabled={action.isPending || !ready}
              onClick={() => action.mutate("buy")}
            >
              {native
                ? `Subscribe${product ? ` · ${product.displayPrice}/year` : ""}`
                : "Subscribe · $10/year"}
            </Button>
          )}
          {data.has_stripe_customer && (
            <Button
              variant="outline"
              disabled={action.isPending}
              onClick={() => action.mutate("manageWeb")}
            >
              Manage web membership
            </Button>
          )}
          {native && (
            <Button
              variant="outline"
              disabled={action.isPending}
              onClick={() => action.mutate("manageApple")}
            >
              Manage App Store membership
            </Button>
          )}
          {native && (
            <Button
              variant="outline"
              disabled={action.isPending || !data.apple_product_id}
              onClick={() => action.mutate("restore")}
            >
              Restore purchases
            </Button>
          )}
          <Button
            variant="outline"
            disabled={action.isPending}
            onClick={() => action.mutate("refresh")}
          >
            Refresh membership
          </Button>
        </div>
        {data.enforcement_active && !data.active && !ready && (
          <p>
            {productError ||
              "Membership purchasing is not available in this environment yet."}
          </p>
        )}
        {notice && <p role="status">{notice}</p>}
        {action.error && (
          <p role="alert" className="text-destructive">
            {action.error.message}
          </p>
        )}
      </section>
      {data.enforcement_active &&
        !data.active &&
        data.free_leagues.length > 2 && (
          <section className="cfb-panel space-y-3 p-5">
            <h2 className="cfb-section-title">Your two free leagues</h2>
            <p>
              Other leagues remain available to read. Choose two leagues to
              manage for free this season. Your selection stays fixed for the
              season; Pro unlocks every league.
            </p>
            {data.free_leagues.map((league) => (
              <label key={league.id} className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={freeIds.includes(league.id)}
                  disabled={
                    selection.isPending ||
                    data.free_league_choice_locked ||
                    (!freeIds.includes(league.id) && freeIds.length >= 2)
                  }
                  onChange={(event) =>
                    setFreeIds((ids) =>
                      event.target.checked
                        ? [...ids, league.id]
                        : ids.filter((id) => id !== league.id),
                    )
                  }
                />
                {league.name}
              </label>
            ))}
            {!data.free_league_choice_locked && (
              <Button
                disabled={selection.isPending || freeIds.length !== 2}
                onClick={() => selection.mutate()}
              >
                Save free leagues for this season
              </Button>
            )}
            {data.free_league_choice_locked && (
              <p>Your free leagues are selected for this season.</p>
            )}
            {selection.error && <p role="alert">{selection.error.message}</p>}
          </section>
        )}
      <div className="grid gap-5 md:grid-cols-2">
        <section className="cfb-panel p-5">
          <h2 className="cfb-section-title">Free</h2>
          <p>
            Up to two leagues each season. Standard scoring refresh and player
            silhouettes.
          </p>
        </section>
        <section className="cfb-panel space-y-2 p-5">
          <h2 className="cfb-section-title">Pro · $10 USD/year</h2>
          <ul className="list-disc space-y-2 pl-5">
            <li>Unlimited leagues</li>
            <li>More frequent live-scoring refresh</li>
            <li>Available player pictures</li>
            <li>Dynasty leagues</li>
            <li>Weekly challenge participation</li>
          </ul>
          <p className="text-sm text-muted-foreground">
            Live data depends on the scoring provider. More frequent refresh
            checks do not increase the provider feed speed.
          </p>
        </section>
      </div>
      <p className="text-sm text-muted-foreground">
        Annual subscriptions renew automatically unless cancelled. Manage
        renewal with the provider you purchased from. Access continues through
        your paid period. App Store purchases use the price shown by Apple.
      </p>
      <nav className="flex gap-4 text-sm">
        <Link to="/terms">Terms</Link>
        <Link to="/privacy">Privacy</Link>
        <Link to="/support">Support</Link>
      </nav>
    </main>
  );
}
