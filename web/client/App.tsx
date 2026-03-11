import "./global.css";

import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";
import WaiverWire from "./pages/WaiverWire";
import Leagues from "./pages/Leagues";
import Settings from "./pages/Settings";
import LeagueDetail from "./pages/LeagueDetail";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import CreateLeague from "./pages/CreateLeague";
import JoinLeague from "./pages/JoinLeague";
import DraftLobby from "./pages/DraftLobby";
import Chats from "./pages/Chats";
import Watchlist from "./pages/Watchlist";
import Rosters from "./pages/Rosters";
import Trade from "./pages/Trade";
import InjuryCenter from "./pages/InjuryCenter";
import Alerts from "./pages/Alerts";
import Stats from "./pages/Stats";

// Placeholder for other routes
const Placeholder = ({ title }: { title: string }) => (
  <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-4">
    <h2 className="text-4xl font-extrabold text-foreground">{title}</h2>
    <p className="text-muted-foreground text-lg max-w-md">
      This page is under construction. Continue prompting to fill in this page contents!
    </p>
  </div>
);

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/leagues" element={<Leagues />} />
            <Route path="/leagues/create" element={<CreateLeague />} />
            <Route path="/leagues/join" element={<JoinLeague />} />
            <Route path="/join/:inviteCode" element={<JoinLeague />} />
            <Route path="/draft" element={<Navigate to="/league/saturday-league" replace />} />
            <Route path="/league/:leagueId" element={<LeagueDetail />} />
            <Route path="/league/:leagueId/lobby" element={<DraftLobby />} />
            <Route path="/waiver-wire" element={<WaiverWire />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/chats" element={<Chats />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/rosters" element={<Rosters />} />
            <Route path="/trade/:leagueId/:playerId" element={<Trade />} />
            <Route path="/injuries" element={<InjuryCenter />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/stats/players" element={<Stats />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/my-team" element={<Placeholder title="My Team" />} />
            <Route path="/matchup" element={<Placeholder title="Matchup" />} />
            <Route path="/scoreboard" element={<Placeholder title="Scoreboard" />} />
            <Route path="/league-news" element={<Placeholder title="League News" />} />
            <Route path="/power-rankings" element={<Placeholder title="Power Rankings" />} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
