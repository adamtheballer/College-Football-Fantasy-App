import "./global.css";

import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/hooks/use-auth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";
import Leagues from "./pages/Leagues";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import CreateLeague from "./pages/CreateLeague";
import JoinLeague from "./pages/JoinLeague";
import LeagueMatchup from "./pages/LeagueMatchup";
import LeagueRoster from "./pages/LeagueRoster";
import LeagueSettings from "./pages/LeagueSettings";
import LeagueWaivers from "./pages/LeagueWaivers";
import DraftHome from "./pages/DraftHome";
import DraftLobby from "./pages/DraftLobby";
import Draft from "./pages/Draft";
import SinglePlayerMockDraftRoom from "./pages/SinglePlayerMockDraftRoom";
import Rosters from "./pages/Rosters";
import Alerts from "./pages/Alerts";
import Stats from "./pages/Stats";
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
