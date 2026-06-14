import { useNavigate } from "react-router-dom";
import { CalendarClock, ClipboardList, Loader2, Plus, Trophy, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLeagues } from "@/hooks/use-leagues";
import { useRecentMockDrafts } from "@/hooks/use-mock-drafts";

export default function DraftHome() {
  const navigate = useNavigate();
  const { data: leagues = [], isLoading: leaguesLoading } = useLeagues(12);
  const { data: recentMocks, isLoading: mocksLoading } = useRecentMockDrafts();
  const realDraftLeagues = leagues.filter((league) =>
    ["scheduled", "live", "paused"].includes(league.draft?.status ?? "")
  );

  return (
    <div className="mx-auto max-w-7xl space-y-6 py-8">
      <Card className="overflow-hidden rounded-[2rem] border-white/10 bg-card/45">
        <CardHeader className="space-y-4">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100">
            <Trophy className="h-4 w-4" />
            Draft Center
          </div>
          <CardTitle className="text-5xl font-black italic uppercase text-foreground">
            Drafts without
            <span className="block bg-gradient-to-r from-cyan-300 via-blue-300 to-emerald-200 bg-clip-text text-transparent">
              crossed wires
            </span>
          </CardTitle>
          <p className="max-w-3xl text-sm font-bold uppercase tracking-[0.14em] text-muted-foreground">
            Real league drafts stay tied to leagues. Mock drafts are standalone practice rooms with invite codes, bots, timers, and disposable results.
          </p>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <Button
            className="h-14 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 text-[11px] font-black uppercase tracking-[0.2em] text-slate-950"
            onClick={() => navigate("/draft/mock/create")}
          >
            <Plus className="mr-2 h-4 w-4" />
            Create Multiplayer Mock
          </Button>
          <Button
            variant="outline"
            className="h-14 rounded-2xl text-[11px] font-black uppercase tracking-[0.2em]"
            onClick={() => navigate("/draft/mock/join")}
          >
            <Users className="mr-2 h-4 w-4" />
            Join Mock By Code
          </Button>
          <Button
            variant="outline"
            className="h-14 rounded-2xl text-[11px] font-black uppercase tracking-[0.2em]"
            onClick={() => navigate("/draft/mock/create?single=1")}
          >
            <ClipboardList className="mr-2 h-4 w-4" />
            Start Single-Player Mock
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="rounded-[2rem] border-white/10 bg-card/40">
          <CardHeader>
            <CardTitle className="text-[12px] font-black uppercase tracking-[0.24em] text-primary">Real League Drafts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {leaguesLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading leagues...</div>
            ) : realDraftLeagues.length === 0 ? (
              <p className="text-sm font-semibold text-muted-foreground">No scheduled or live real drafts.</p>
            ) : (
              realDraftLeagues.map((league) => (
                <button
                  key={league.id}
                  type="button"
                  className="flex w-full items-center justify-between rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-left hover:bg-white/[0.06]"
                  onClick={() => navigate(league.draft?.status === "live" ? `/league/${league.id}/draft` : `/league/${league.id}/lobby`)}
                >
                  <div>
                    <p className="font-black text-foreground">{league.name}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">Real draft writes league rosters</p>
                  </div>
                  <CalendarClock className="h-5 w-5 text-primary" />
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="rounded-[2rem] border-white/10 bg-card/40">
          <CardHeader>
            <CardTitle className="text-[12px] font-black uppercase tracking-[0.24em] text-primary">Recent Mock Drafts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {mocksLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading mocks...</div>
            ) : !recentMocks?.data?.length ? (
              <p className="text-sm font-semibold text-muted-foreground">No recent mock drafts.</p>
            ) : (
              recentMocks.data.map((mock) => (
                <button
                  key={mock.id}
                  type="button"
                  className="flex w-full items-center justify-between rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-left hover:bg-white/[0.06]"
                  onClick={() => navigate(`/draft/mock/${mock.id}/${mock.status === "completed" ? "results" : mock.can_enter_room ? "room" : "lobby"}`)}
                >
                  <div>
                    <p className="font-black text-foreground">{mock.name}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                      {mock.joined_count}/{mock.team_count} joined • {mock.status}
                    </p>
                  </div>
                  <Users className="h-5 w-5 text-cyan-200" />
                </button>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
