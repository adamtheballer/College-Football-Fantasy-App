import { Link } from "react-router-dom";
import { ArrowLeft, Bot, ClipboardList, ShieldCheck, Sparkles, Trophy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useLeagues } from "@/hooks/use-leagues";

const formatDraftTime = (value?: string | null) => {
  if (!value) return "Draft not scheduled";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Draft not scheduled";
  return parsed.toLocaleString();
};

export default function DraftHome() {
  const { data: leagues = [] } = useLeagues(20, true);
  const realDrafts = leagues.filter(
    (league) =>
      league.status === "draft_live" ||
      league.status === "draft_scheduled" ||
      league.draft?.status === "live" ||
      league.draft?.status === "scheduled"
  );

  return (
    <div className="relative max-w-7xl mx-auto space-y-8 pb-20 pt-12">
      <div className="pointer-events-none absolute -left-32 top-8 h-72 w-72 rounded-full bg-cyan-400/20 blur-[90px]" />
      <div className="pointer-events-none absolute right-0 top-24 h-80 w-80 rounded-full bg-amber-300/14 blur-[100px]" />
      <div className="pointer-events-none absolute bottom-0 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-fuchsia-500/12 blur-[100px]" />

      <Card className="relative overflow-hidden rounded-[2.75rem] border border-cyan-200/20 bg-[linear-gradient(135deg,rgba(8,47,73,0.92),rgba(15,23,42,0.78)_44%,rgba(49,22,78,0.82))] shadow-[0_0_100px_rgba(34,211,238,0.18)] backdrop-blur-xl">
        <div className="absolute inset-0 opacity-[0.18] [background-image:linear-gradient(rgba(255,255,255,0.18)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.12)_1px,transparent_1px)] [background-size:56px_56px]" />
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-sky-300/25 blur-[70px]" />
        <div className="absolute bottom-0 left-8 h-48 w-48 rounded-full bg-amber-300/18 blur-[80px]" />
        <CardContent className="relative p-8 md:p-12 space-y-8">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="inline-flex w-fit items-center gap-3 rounded-full border border-cyan-200/30 bg-cyan-300/10 px-5 py-3 text-[10px] font-black uppercase tracking-[0.28em] text-cyan-100 shadow-[0_0_24px_rgba(34,211,238,0.16)]">
              <Trophy className="h-4 w-4 text-amber-200" />
              Draft Center
            </div>
            <Button
              asChild
              variant="outline"
              className="h-12 w-fit rounded-2xl border-white/20 bg-white/10 px-5 text-[10px] font-black uppercase tracking-[0.2em] text-white hover:bg-white/15"
            >
              <Link to="/">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Exit to Dashboard
              </Link>
            </Button>
          </div>
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-200/25 bg-amber-300/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.22em] text-amber-100">
              <Sparkles className="h-3.5 w-3.5" />
              Practice room
            </div>
            <h1 className="max-w-6xl text-5xl md:text-7xl font-black italic uppercase tracking-tight text-transparent bg-gradient-to-r from-white via-cyan-100 to-amber-100 bg-clip-text">
              Practice without touching leagues
            </h1>
            <p className="max-w-4xl text-sm md:text-lg font-bold uppercase tracking-[0.18em] text-slate-200/78">
              Single-player mock drafts are local practice rooms. Real league drafts stay tied to
              league hubs and create real roster entries only inside league draft rooms.
            </p>
          </div>
          <div className="flex flex-col gap-4 md:flex-row">
            <Button
              asChild
              className="h-16 rounded-[1.5rem] bg-gradient-to-r from-cyan-300 to-blue-500 px-8 text-[11px] font-black uppercase tracking-[0.24em] text-slate-950 shadow-[0_20px_45px_rgba(56,189,248,0.25)] hover:from-cyan-200 hover:to-blue-400"
            >
              <Link to="/draft/mock/single-player?new=1">
                <Bot className="mr-3 h-5 w-5" />
                Start Single-Player Mock
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              className="h-16 rounded-[1.5rem] border-white/20 bg-white/10 px-8 text-[11px] font-black uppercase tracking-[0.24em] text-white hover:bg-white/15"
            >
              <Link to="/leagues">
                <ClipboardList className="mr-3 h-5 w-5" />
                Find Real League Drafts
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="overflow-hidden rounded-[2.5rem] border border-sky-300/16 bg-gradient-to-br from-sky-500/12 via-card/45 to-blue-950/40 shadow-[0_30px_70px_rgba(14,165,233,0.08)]">
          <CardContent className="p-8 space-y-5">
            <p className="text-[10px] font-black uppercase tracking-[0.32em] text-cyan-200">
              Real League Drafts
            </p>
            {realDrafts.length === 0 ? (
              <p className="text-sm font-bold uppercase tracking-[0.18em] text-muted-foreground">
                No scheduled or live real drafts.
              </p>
            ) : (
              <div className="space-y-3">
                {realDrafts.map((league) => (
                  <Link
                    key={league.id}
                    to={`/league/${league.id}/draft`}
                    className="block rounded-3xl border border-white/10 bg-white/[0.06] p-5 transition hover:border-cyan-200/40 hover:bg-cyan-300/10"
                  >
                    <p className="text-lg font-black uppercase tracking-tight text-foreground">
                      {league.name}
                    </p>
                    <p className="mt-2 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
                      {formatDraftTime(league.draft?.draft_datetime_utc)}
                    </p>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="overflow-hidden rounded-[2.5rem] border border-amber-200/16 bg-gradient-to-br from-amber-300/12 via-card/45 to-fuchsia-950/30 shadow-[0_30px_70px_rgba(251,191,36,0.08)]">
          <CardContent className="p-8 space-y-5">
            <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.32em] text-amber-100">
              <ShieldCheck className="h-4 w-4" />
              Single-Player Mock Rules
            </p>
            <div className="space-y-3 text-sm font-bold uppercase tracking-[0.14em] text-slate-200/74">
              <p>12 teams • snake order • 13 rounds</p>
              <p>Bot picks advance automatically after about two seconds</p>
              <p>Your timer auto-picks from queue first, then best available</p>
              <p>No real DraftPick, RosterEntry, League status, trades, or standings are touched</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
