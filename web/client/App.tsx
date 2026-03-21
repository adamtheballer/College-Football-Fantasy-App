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
import LeagueDetail from "./pages/LeagueDetail";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import CreateLeague from "./pages/CreateLeague";
import JoinLeague from "./pages/JoinLeague";
import DraftLobby from "./pages/DraftLobby";
import Draft from "./pages/Draft";
import Rosters from "./pages/Rosters";
import Alerts from "./pages/Alerts";
import Stats from "./pages/Stats";
import WaiverWire from "./pages/WaiverWire";
import Watchlist from "./pages/Watchlist";

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
              <Route path="/draft" element={<Navigate to="/leagues" replace />} />
              <Route
                path="/league/:leagueId"
                element={
                  <ProtectedRoute>
                    <LeagueDetail />
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
              <Route path="/waivers" element={<ProtectedRoute><WaiverWire /></ProtectedRoute>} />
              <Route path="/watchlists" element={<ProtectedRoute><Watchlist /></ProtectedRoute>} />
              <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
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
