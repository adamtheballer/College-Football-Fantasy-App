import "./global.css";

import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/hooks/use-auth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ApiError } from "@/lib/api";
import Layout from "./components/Layout";

const Index = lazy(() => import("./pages/Index"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Leagues = lazy(() => import("./pages/Leagues"));
const Settings = lazy(() => import("./pages/Settings"));
const Login = lazy(() => import("./pages/Login"));
const Signup = lazy(() => import("./pages/Signup"));
const PasswordResetConfirm = lazy(() => import("./pages/PasswordResetConfirm"));
const CreateLeague = lazy(() => import("./pages/CreateLeague"));
const JoinLeague = lazy(() => import("./pages/JoinLeague"));
const LeagueMatchup = lazy(() => import("./pages/LeagueMatchup"));
const LeagueRoster = lazy(() => import("./pages/LeagueRoster"));
const LeagueSettings = lazy(() => import("./pages/LeagueSettings"));
const LeagueWaivers = lazy(() => import("./pages/LeagueWaivers"));
const LeagueWatchlist = lazy(() => import("./pages/LeagueWatchlist"));
const DraftHome = lazy(() => import("./pages/DraftHome"));
const DraftLobby = lazy(() => import("./pages/DraftLobby"));
const Draft = lazy(() => import("./pages/Draft"));
const SinglePlayerMockDraftRoom = lazy(() => import("./pages/SinglePlayerMockDraftRoom"));
const Rosters = lazy(() => import("./pages/Rosters"));
const Alerts = lazy(() => import("./pages/Alerts"));
const PlayerCompare = lazy(() => import("./pages/PlayerCompare"));
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

const RouteFallback = () => (
  <div className="flex min-h-[45vh] items-center justify-center">
    <div className="rounded-[2rem] border border-sky-300/20 bg-slate-950/55 px-8 py-6 text-[11px] font-black uppercase tracking-[0.22em] text-sky-200 shadow-[0_0_40px_rgba(56,189,248,0.12)]">
      Loading view...
    </div>
  </div>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
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
                <Route path="/rosters" element={<ProtectedRoute><Rosters /></ProtectedRoute>} />
                <Route path="/chats" element={<ProtectedRoute><Chats /></ProtectedRoute>} />
                <Route path="/waivers" element={<ProtectedRoute><Navigate to="/leagues" replace /></ProtectedRoute>} />
                <Route path="/watchlists" element={<ProtectedRoute><Navigate to="/leagues" replace /></ProtectedRoute>} />
                <Route path="/injury-center" element={<ProtectedRoute><InjuryCenter /></ProtectedRoute>} />
                <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
                <Route path="/trade" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/trade/:leagueId/:playerId" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/leagues/:leagueId/trades/:tradeId" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/admin/scoring" element={<ProtectedRoute><AdminScoring /></ProtectedRoute>} />
                <Route path="/player-compare" element={<PlayerCompare />} />
                <Route path="/stats" element={<Navigate to="/player-compare" replace />} />
                <Route path="/stats/players" element={<Navigate to="/player-compare" replace />} />
                <Route path="/login" element={<Login />} />
                <Route path="/signup" element={<Signup />} />
                <Route path="/verify-email" element={<Navigate to="/leagues" replace />} />
                <Route path="/password-reset/confirm" element={<PasswordResetConfirm />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </Layout>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
