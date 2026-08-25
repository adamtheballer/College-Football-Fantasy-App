import "./global.css";

import { Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import { AuthProvider } from "@/hooks/use-auth";
import { AppErrorBoundary } from "@/components/AppErrorBoundary";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { SkeletonState } from "@/components/states";
import { ApiError } from "@/lib/api";
import RuntimeCompatibilityGate from "@/components/RuntimeCompatibilityGate";
import { lazyWithRouteRecovery } from "@/lib/lazyWithRouteRecovery";
import Layout from "./components/Layout";

const Index = lazyWithRouteRecovery(() => import("./pages/Index"));
const NotFound = lazyWithRouteRecovery(() => import("./pages/NotFound"));
const Leagues = lazyWithRouteRecovery(() => import("./pages/Leagues"));
const Settings = lazyWithRouteRecovery(() => import("./pages/Settings"));
const ReportBug = lazyWithRouteRecovery(() => import("./pages/ReportBug"));
const Login = lazyWithRouteRecovery(() => import("./pages/Login"));
const ResetPassword = lazyWithRouteRecovery(() => import("./pages/ResetPassword"));
const ForgotPassword = lazyWithRouteRecovery(() => import("./pages/ForgotPassword"));
const CreateLeague = lazyWithRouteRecovery(() => import("./pages/CreateLeague"));
const JoinLeague = lazyWithRouteRecovery(() => import("./pages/JoinLeague"));
const LeagueMatchup = lazyWithRouteRecovery(() => import("./pages/LeagueMatchup"));
const LeagueRoster = lazyWithRouteRecovery(() => import("./pages/LeagueRoster"));
const LeagueSettings = lazyWithRouteRecovery(() => import("./pages/LeagueSettings"));
const LeagueWaivers = lazyWithRouteRecovery(() => import("./pages/LeagueWaivers"));
const LeagueWatchlist = lazyWithRouteRecovery(() => import("./pages/LeagueWatchlist"));
const DraftHome = lazyWithRouteRecovery(() => import("./pages/DraftHome"));
const DraftLobby = lazyWithRouteRecovery(() => import("./pages/DraftLobby"));
const Draft = lazyWithRouteRecovery(() => import("./pages/Draft"));
const SinglePlayerMockDraftRoom = lazyWithRouteRecovery(() => import("./pages/SinglePlayerMockDraftRoom"));
const Rosters = lazyWithRouteRecovery(() => import("./pages/Rosters"));
const Alerts = lazyWithRouteRecovery(() => import("./pages/Alerts"));
const Chats = lazyWithRouteRecovery(() => import("./pages/Chats"));
const InjuryCenter = lazyWithRouteRecovery(() => import("./pages/InjuryCenter"));
const Trade = lazyWithRouteRecovery(() => import("./pages/Trade"));
const AdminScoring = lazyWithRouteRecovery(() => import("./pages/AdminScoring"));
const ComingSoon = lazyWithRouteRecovery(() => import("./pages/ComingSoon"));
const SaturdayPick6 = lazyWithRouteRecovery(() => import("./pages/SaturdayPick6"));
const PrivacyPolicy = lazyWithRouteRecovery(() => import("./pages/PrivacyPolicy"));
const TermsOfUse = lazyWithRouteRecovery(() => import("./pages/TermsOfUse"));
const ProviderDisclosure = lazyWithRouteRecovery(() => import("./pages/ProviderDisclosure"));
const Support = lazyWithRouteRecovery(() => import("./pages/Support"));

const NON_RETRYABLE_STATUSES = new Set([401, 403, 404]);

const shouldRetryQuery = (failureCount: number, error: unknown) => {
  if (error instanceof ApiError && NON_RETRYABLE_STATUSES.has(error.status)) {
    return false;
  }
  return failureCount < 3;
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetryQuery,
    },
    mutations: {
      retry: shouldRetryQuery,
    },
  },
});

const RouteFallback = () => (
  <div className="mx-auto w-full max-w-6xl py-5">
    <SkeletonState rows={5} label="Loading view" />
  </div>
);

const LegacyPlayoffsRedirect = () => {
  const { leagueId } = useParams();
  return <Navigate replace to={leagueId ? `/league/${leagueId}/settings?section=playoffs` : "/leagues"} />;
};

const ApplicationRoutes = () => (
  <RuntimeCompatibilityGate>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <AppErrorBoundary>
          <Layout>
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<Index />} />
                <Route path="/leagues" element={<Leagues />} />
                <Route
                  path="/leagues/create"
                  element={
                    <ProtectedRoute>
                      <CreateLeague />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/leagues/join"
                  element={
                    <ProtectedRoute>
                      <JoinLeague />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/join/:inviteCode"
                  element={
                    <ProtectedRoute>
                      <JoinLeague />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/draft"
                  element={
                    <ProtectedRoute>
                      <DraftHome />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/draft/mock/single-player"
                  element={
                    <ProtectedRoute>
                      <SinglePlayerMockDraftRoom />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId"
                  element={
                    <ProtectedRoute>
                      <LeagueRoster />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/roster"
                  element={
                    <ProtectedRoute>
                      <LeagueRoster />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/matchup"
                  element={
                    <ProtectedRoute>
                      <LeagueMatchup />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/playoffs"
                  element={
                    <ProtectedRoute>
                      <LegacyPlayoffsRedirect />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/waivers"
                  element={
                    <ProtectedRoute>
                      <LeagueWaivers />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/watchlist"
                  element={
                    <ProtectedRoute>
                      <LeagueWatchlist />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/settings"
                  element={
                    <ProtectedRoute>
                      <LeagueSettings />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/lobby"
                  element={
                    <ProtectedRoute>
                      <DraftLobby />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/draft"
                  element={
                    <ProtectedRoute>
                      <Draft />
                    </ProtectedRoute>
                  }
                />
                <Route path="/settings" element={<Settings />} />
                <Route path="/report-bug" element={<ReportBug />} />
                <Route path="/rosters" element={<ProtectedRoute><Rosters /></ProtectedRoute>} />
                <Route path="/chats" element={<ProtectedRoute><Chats /></ProtectedRoute>} />
                <Route path="/waivers" element={<ProtectedRoute><Navigate to="/leagues" replace /></ProtectedRoute>} />
                <Route path="/watchlists" element={<ProtectedRoute><Navigate to="/leagues" replace /></ProtectedRoute>} />
                <Route path="/injury-center" element={<ProtectedRoute><InjuryCenter /></ProtectedRoute>} />
                <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
                <Route path="/trade" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/trade/:leagueId/:playerId" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/leagues/:leagueId/trades/:tradeId" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/coming-soon" element={<ProtectedRoute><ComingSoon /></ProtectedRoute>} />
                <Route path="/saturday-pick-6" element={<ProtectedRoute><SaturdayPick6 /></ProtectedRoute>} />
                <Route path="/admin/scoring" element={<ProtectedRoute><AdminScoring /></ProtectedRoute>} />
                <Route path="/stats" element={<Navigate to="/leagues" replace />} />
                <Route path="/stats/players" element={<Navigate to="/leagues" replace />} />
                <Route path="/login" element={<Login />} />
                {/* Keep old shared links functional without reviving the retired Pro claim flow. */}
                <Route path="/beta-access" element={<Navigate to="/login" replace />} />
                <Route path="/signup" element={<Navigate to="/login?flow=signup" replace />} />
                <Route path="/reset-password" element={<ResetPassword />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </Layout>
        </AppErrorBoundary>
      </TooltipProvider>
    </AuthProvider>
  </RuntimeCompatibilityGate>
);

// Policy documents must remain readable in a fresh, logged-out browser even
// if the authenticated app's API runtime is unavailable or mid-deployment.
// Keep these first-party routes outside the auth provider, app shell, and
// runtime compatibility gate instead of letting a release diagnostic block a
// required public document.
const App = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/terms" element={<TermsOfUse />} />
          <Route path="/provider-disclosure" element={<ProviderDisclosure />} />
          <Route path="/support" element={<Support />} />
          <Route path="*" element={<ApplicationRoutes />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;
