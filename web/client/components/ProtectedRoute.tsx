import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { PageLoadingState } from "@/components/PageState";
import { useAuth } from "@/hooks/use-auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isBootstrapping, isLoggedIn } = useAuth();

  if (isBootstrapping) {
    return <PageLoadingState title="Validating session" description="Checking your active sign-in before opening this screen." />;
  }

  if (!isLoggedIn) {
    const from = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to="/login" replace state={{ from }} />;
  }

  return <>{children}</>;
}
