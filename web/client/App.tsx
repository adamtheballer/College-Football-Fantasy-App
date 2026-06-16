import "./global.css";

import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { lazy, Suspense } from "react";
import { AuthProvider } from "@/hooks/use-auth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Layout from "./components/Layout";
import { ApiError } from "@/lib/api";

const Index = lazy(() => import("./pages/Index"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Leagues = lazy(() => import("./pages/Leagues"));
const Settings = lazy(() => import("./pages/Settings"));
const LeagueDetail = lazy(() => import("./pages/LeagueDetail"));
const Lineup = lazy(() => import("./pages/Lineup"));
const MatchupDetail = lazy(() => import("./pages/MatchupDetail"));
const Login = lazy(() => import("./pages/Login"));
const Signup = lazy(() => import("./pages/Signup"));
const CreateLeague = lazy(() => import("./pages/CreateLeague"));
const JoinLeague = lazy(() => import("./pages/JoinLeague"));
const Draft = lazy(() => import("./pages/Draft"));
const DraftLobby = lazy(() => import("./pages/DraftLobby"));
const DraftHome = lazy(() => import("./pages/DraftHome"));
const CreateMockDraft = lazy(() => import("./pages/CreateMockDraft"));
const JoinMockDraft = lazy(() => import("./pages/JoinMockDraft"));
const MockDraftLobby = lazy(() => import("./pages/MockDraftLobby"));
const MockDraftRoom = lazy(() => import("./pages/MockDraftRoom"));
const SinglePlayerMockDraftRoom = lazy(() => import("./pages/SinglePlayerMockDraftRoom"));
const MockDraftResults = lazy(() => import("./pages/MockDraftResults"));
const Rosters = lazy(() => import("./pages/Rosters"));
const Stats = lazy(() => import("./pages/Stats"));
const WaiverWire = lazy(() => import("./pages/WaiverWire"));
const Watchlist = lazy(() => import("./pages/Watchlist"));
const Chats = lazy(() => import("./pages/Chats"));
const InjuryCenter = lazy(() => import("./pages/InjuryCenter"));
const Trade = lazy(() => import("./pages/Trade"));

const shouldRetryQuery = (failureCount: number, error: unknown) => {
  if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
    return false;
  }
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return false;
  }
  return failureCount < 2;
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetryQuery,
      staleTime: 15_000,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: (failureCount, error) => shouldRetryQuery(failureCount, error),
    },
  },
});

const RouteFallback = () => (
  <div className="flex min-h-[40vh] items-center justify-center px-6 py-16">
    <div className="rounded-2xl border border-white/10 bg-card/60 px-5 py-4 text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground">
      Loading...
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
                  path="/draft/mock/create"
                  element={
                    <ProtectedRoute>
                      <CreateMockDraft />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/draft/mock/join"
                  element={
                    <ProtectedRoute>
                      <JoinMockDraft />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/draft/mock/invite/:inviteToken"
                  element={
                    <ProtectedRoute>
                      <JoinMockDraft />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/draft/mock/:mockDraftId/lobby"
                  element={
                    <ProtectedRoute>
                      <MockDraftLobby />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/draft/mock/:mockDraftId/room"
                  element={
                    <ProtectedRoute>
                      <MockDraftRoom />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/draft/mock/single/:mockDraftId"
                  element={
                    <ProtectedRoute>
                      <SinglePlayerMockDraftRoom />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/draft/mock/:mockDraftId/results"
                  element={
                    <ProtectedRoute>
                      <MockDraftResults />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/mock-drafts/:mockDraftId/lobby"
                  element={
                    <ProtectedRoute>
                      <MockDraftLobby />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/mock-drafts/:mockDraftId/room"
                  element={
                    <ProtectedRoute>
                      <MockDraftRoom />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/mock-drafts/:mockDraftId/board"
                  element={
                    <ProtectedRoute>
                      <MockDraftRoom />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId"
                  element={
                    <ProtectedRoute>
                      <LeagueDetail />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/lineup"
                  element={
                    <ProtectedRoute>
                      <Lineup />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/league/:leagueId/matchup/:matchupId"
                  element={
                    <ProtectedRoute>
                      <MatchupDetail />
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
                <Route path="/waivers" element={<ProtectedRoute><WaiverWire /></ProtectedRoute>} />
                <Route path="/watchlists" element={<ProtectedRoute><Watchlist /></ProtectedRoute>} />
                <Route path="/injury-center" element={<ProtectedRoute><InjuryCenter /></ProtectedRoute>} />
                <Route path="/trade" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/trade/:leagueId" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/trade/:leagueId/:playerId" element={<ProtectedRoute><Trade /></ProtectedRoute>} />
                <Route path="/stats" element={<Stats />} />
                <Route path="/stats/players" element={<Stats />} />
                <Route path="/login" element={<Login />} />
                <Route path="/signup" element={<Signup />} />
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
