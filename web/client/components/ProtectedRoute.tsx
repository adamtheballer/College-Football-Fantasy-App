import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isBootstrapping, isLoggedIn } = useAuth();

  if (isBootstrapping) {
    return (
      <div className="max-w-3xl mx-auto py-20">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardContent className="p-12 text-center">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
              Validating session...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!isLoggedIn) {
    const from = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to="/login" replace state={{ from }} />;
  }

  return <>{children}</>;
}
