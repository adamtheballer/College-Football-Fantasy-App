import { useEffect } from "react";
import { useAuth } from "@/hooks/use-auth";
import { trackProductEvent } from "@/lib/product-analytics";
export function ProductSession() {
  const { user, isBootstrapping } = useAuth();
  useEffect(() => {
    if (!user || isBootstrapping) return;
    const record = () => {
      if (document.visibilityState === "visible")
        void trackProductEvent(user.id, "session");
    };
    record();
    document.addEventListener("visibilitychange", record);
    return () => document.removeEventListener("visibilitychange", record);
  }, [user?.id, isBootstrapping]);
  return null;
}
