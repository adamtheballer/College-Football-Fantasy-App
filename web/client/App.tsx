import "./global.css";

import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/hooks/use-auth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageErrorBoundary } from "@/components/PageErrorBoundary";
import { PageLoadingState } from "@/components/PageState";
import { ApiError } from "@/lib/api";
import Layout from "./components/Layout";

const Index = lazy(() => import("./pages/Index"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Leagues = lazy(() => import("./pages/Leagues"));
const Settings = lazy(() => import("./pages/Settings"));
const Login = lazy(() => import("./pages/Login"));
const Signup = lazy(() => import("./pages/Signup"));
const VerifyEmail = lazy(() => import("./pages/VerifyEmail"));
const PasswordResetRequest = lazy(() => import("./pages/PasswordResetRequest"));
const PasswordResetConfirm = lazy(() => import("./pages/PasswordResetConfirm"));
const CreateLeague = lazy(() => import("./pages/CreateLeague"));
const JoinLeague = lazy(() => import("./pages/JoinLeague"));
const LeagueMatchup = lazy(() => import("./pages/LeagueMatchup"));
const LeagueRoster = lazy(() => import("./pages/LeagueRoster"));
const LeagueSettings = lazy(() => import("./pages/LeagueSettings"));
const LeagueWatchlist = lazy(() => import("./pages/LeagueWatchlist"));
const LeagueWaivers = lazy(() => import("./pages/LeagueWaivers"));
const LeagueInviteMembers = lazy(() => import("./pages/LeagueInviteMembers"));
const DraftHome = lazy(() => import("./pages/DraftHome"));
const DraftLobby = lazy(() => import("./pages/DraftLobby"));
const Draft = lazy(() => import("./pages/Draft"));
const SinglePlayerMockDraftRoom = lazy(() => import("./pages/SinglePlayerMockDraftRoom"));
const Rosters = lazy(() => import("./pages/Rosters"));
const Alerts = lazy(() => import("./pages/Alerts"));
const Stats = lazy(() => import("./pages/Stats"));
const Chats = lazy(() => import("./pages/Chats"));
const InjuryCenter = lazy(() => import("./pages/InjuryCenter"));
const Trade = lazy(() => import("./pages/Trade"));
const AdminScoring = lazy(() => import("./pages/AdminScoring"));

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

const RouteFallback = () => <PageLoadingState title="Loading view" description="Preparing this screen." />;

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Layout>
            <PageErrorBoundary>
              <Suspense fallback={<RouteFallback />}>
                <Routes>
                <Route path="/" element={<ProtectedRoute><Index /></ProtectedRoute>} />
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
                  path="/league/:leagueId/waivers"
                  element={
                    <ProtectedRoute>
                      <LeagueWaivers />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/invite"
                  element={
                    <ProtectedRoute>
                      <LeagueInviteMembers />
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
                <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                <Route path="/rosters" element={<ProtectedRoute><Rosters /></ProtectedRoute>} />
                <Route path="/chats" element={<ProtectedRoute><Chats /></ProtectedRoute>} />
                <Route path="/waivers" element={<ProtectedRoute><Navigate to="/leagues" replace /></ProtectedRoute>} />
                <Route path="/watchlists" element={<ProtectedRoute><Navigate to="/leagues" replace /></ProtectedRoute>} />
                <Route path="/injury-center" element={<ProtectedRoute><InjuryCenter /></ProtectedRoute>} />
                <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
                <Route path="/trade" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/trade/:leagueId" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/trade/:leagueId/:playerId" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/admin/scoring" element={<ProtectedRoute><AdminScoring /></ProtectedRoute>} />
                <Route path="/stats" element={<Stats />} />
                <Route path="/stats/players" element={<Stats />} />
                <Route path="/login" element={<Login />} />
                <Route path="/signup" element={<Signup />} />
                <Route path="/verify-email" element={<VerifyEmail />} />
                <Route path="/password-reset" element={<PasswordResetRequest />} />
                <Route path="/password-reset/confirm" element={<PasswordResetConfirm />} />
                <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </PageErrorBoundary>
          </Layout>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
