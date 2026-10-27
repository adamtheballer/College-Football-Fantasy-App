import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "./use-auth";
import { membershipApi, type Membership } from "@/lib/membership";
import {
  isNativeMembership,
  nativeMembership,
  type StoreTransaction,
} from "@/lib/native-membership";

type Context = {
  enabled: boolean;
  data?: Membership;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
};
const MembershipContext = createContext<Context>({
  enabled: false,
  loading: false,
  error: null,
  refresh: async () => undefined,
});
export const useMembership = () => useContext(MembershipContext);
export const usePlayerPictures = () => {
  const m = useMembership();
  return !m.enabled || m.data?.features.player_pictures === true;
};

export function MembershipProvider({ children }: { children: ReactNode }) {
  if (import.meta.env.VITE_MEMBERSHIP_ENABLED !== "true")
    return <>{children}</>;
  return <EnabledMembership>{children}</EnabledMembership>;
}
function EnabledMembership({ children }: { children: ReactNode }) {
  const { user, isBootstrapping } = useAuth();
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: ["membership", user?.id],
    queryFn: membershipApi.status,
    enabled: !!user && !isBootstrapping,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
    refetchOnWindowFocus: "always",
  });
  useEffect(() => {
    if (
      !user ||
      !query.data?.apple_account_token ||
      !query.data.apple_product_id ||
      !isNativeMembership()
    )
      return;
    const accountToken = query.data.apple_account_token,
      productId = query.data.apple_product_id;
    let disposed = false;
    let remove: (() => void) | undefined;
    const pending = new Set<string>();
    const verify = async (tx: StoreTransaction) => {
      if (
        disposed ||
        tx.appAccountToken.toLowerCase() !== accountToken.toLowerCase() ||
        pending.has(tx.transactionId)
      )
        return;
      pending.add(tx.transactionId);
      try {
        await membershipApi.verifyApple(tx.signedTransaction);
        // Receipt remains unfinished if the server cannot acknowledge ownership.
        await nativeMembership.finish({ transactionId: tx.transactionId });
        if (!disposed)
          await cache.invalidateQueries({ queryKey: ["membership", user.id] });
      } catch {
        /* Unfinished StoreKit receipts are retried on restore/next login. */
      } finally {
        pending.delete(tx.transactionId);
      }
    };
    void nativeMembership
      .addListener("transactionUpdated", (tx) => {
        void verify(tx);
      })
      .then((handle) => {
        if (disposed) void handle.remove();
        else
          remove = () => {
            void handle.remove();
          };
      })
      .catch(() => undefined);
    void nativeMembership
      .restore({ productId, appAccountToken: accountToken, synchronize: false })
      .then(async (result) => {
        for (const tx of result.transactions) await verify(tx);
      })
      .catch(() => undefined);
    return () => {
      disposed = true;
      remove?.();
    };
  }, [
    user?.id,
    query.data?.apple_account_token,
    query.data?.apple_product_id,
    cache,
  ]);
  return (
    <MembershipContext.Provider
      value={{
        enabled: true,
        data: query.data,
        loading: query.isPending && !!user,
        error: query.error,
        refresh: query.refetch,
      }}
    >
      {children}
    </MembershipContext.Provider>
  );
}
