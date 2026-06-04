import "./global.css";

import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/hooks/use-auth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";
import Leagues from "./pages/Leagues";
import Settings from "./pages/Settings";
import LeagueDetail from "./pages/LeagueDetail";
import Lineup from "./pages/Lineup";
import MatchupDetail from "./pages/MatchupDetail";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import CreateLeague from "./pages/CreateLeague";
import JoinLeague from "./pages/JoinLeague";
import Draft from "./pages/Draft";
import DraftLobby from "./pages/DraftLobby";
import DraftHome from "./pages/DraftHome";
import CreateMockDraft from "./pages/CreateMockDraft";
import JoinMockDraft from "./pages/JoinMockDraft";
import MockDraftLobby from "./pages/MockDraftLobby";
import MockDraftRoom from "./pages/MockDraftRoom";
import MockDraftResults from "./pages/MockDraftResults";
import Rosters from "./pages/Rosters";
import Stats from "./pages/Stats";
import WaiverWire from "./pages/WaiverWire";
import Watchlist from "./pages/Watchlist";
import Chats from "./pages/Chats";
import InjuryCenter from "./pages/InjuryCenter";
import Trade from "./pages/Trade";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Layout>
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
          </Layout>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
