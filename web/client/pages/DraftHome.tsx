import { type ReactNode, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, ClipboardList, Clock3, ShieldCheck, Trophy, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useLeagues } from "@/hooks/use-leagues";
import { MOCK_ROUNDS } from "@/lib/singlePlayerMockDraft";
import { cn } from "@/lib/utils";

const LEAGUE_SIZE_OPTIONS = [8, 10, 12];
const TIMER_OPTIONS = [30, 60, 90];

const formatDraftTime = (value?: string | null) => {
  if (!value) return "Draft not scheduled";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Draft not scheduled";
  return parsed.toLocaleString();
};

const OptionButton = ({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  onClick: () => void;
}) => (
  <button
    type="button"
    onClick={onClick}
    className={cn(
      "h-12 rounded-2xl border px-5 text-[11px] font-black uppercase tracking-[0.18em] transition",
      "hover:-translate-y-0.5 hover:border-cyan-200/45 hover:bg-cyan-300/10 hover:shadow-[0_0_26px_rgba(56,189,248,0.16)]",
      active
        ? "border-cyan-200/70 bg-cyan-300/18 text-cyan-50 shadow-[0_0_34px_rgba(56,189,248,0.22)]"
        : "border-white/10 bg-white/[0.045] text-slate-300"
    )}
  >
    {children}
  </button>
);

export default function DraftHome() {
  const { data: leagues = [] } = useLeagues(20, true);
  const [leagueSize, setLeagueSize] = useState(12);
  const [pickTimer, setPickTimer] = useState(30);

  const mockDraftUrl = useMemo(
    () => `/draft/mock/single-player?new=1&teams=${leagueSize}&timer=${pickTimer}`,
    [leagueSize, pickTimer]
  );

  const realDrafts = leagues.filter(
    (league) =>
      league.status === "draft_live" ||
      league.status === "draft_scheduled" ||
      league.draft?.status === "live" ||
      league.draft?.status === "scheduled"
  );

  return (
    <div className="relative mx-auto max-w-[1320px] space-y-7 px-4 py-8 pb-24 md:px-8">
      <div className="pointer-events-none absolute left-0 top-10 h-72 w-72 rounded-full bg-sky-400/12 blur-[92px]" />
      <div className="pointer-events-none absolute right-0 top-40 h-80 w-80 rounded-full bg-blue-500/10 blur-[100px]" />

      <header className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-3">
          <p className="text-[11px] font-black uppercase tracking-[0.32em] text-cyan-200">
            Draft Center
          </p>
          <h1 className="text-5xl font-black italic tracking-[-0.045em] text-white md:text-7xl">
            Draft
          </h1>
          <p className="max-w-3xl text-base font-semibold leading-7 text-slate-300">
            Practice in a single-player mock, preview league drafts, and enter the real draft room only when a league draft is ready.
          </p>
        </div>
        <Button
          asChild
          className="h-14 w-fit rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 px-7 text-[11px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_18px_42px_rgba(56,189,248,0.22)] hover:from-cyan-200 hover:to-blue-400"
        >
          <Link to={mockDraftUrl}>
            <Bot className="mr-3 h-5 w-5" />
            Start Single-Player Mock
          </Link>
        </Button>
      </header>

      <div className="relative grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="overflow-hidden rounded-[2rem] border border-cyan-200/16 bg-[linear-gradient(135deg,rgba(15,23,42,0.88),rgba(8,47,73,0.42),rgba(15,23,42,0.9))] shadow-[0_0_70px_rgba(14,165,233,0.12)]">
          <CardContent className="space-y-7 p-6 md:p-8">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-cyan-200/25 bg-cyan-300/12 text-cyan-100 shadow-[0_0_24px_rgba(34,211,238,0.16)]">
                <Trophy className="h-5 w-5" />
              </div>
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-cyan-200">Mock Draft Setup</p>
                <h2 className="mt-2 text-2xl font-black tracking-tight text-white">Tune the room before you enter</h2>
                <p className="mt-2 max-w-2xl text-sm font-semibold leading-6 text-slate-300">
                  These settings apply to the next new single-player mock. The draft room stays fullscreen; this page stays a normal app tab.
                </p>
              </div>
            </div>

            <div className="grid gap-5">
              <section className="rounded-[1.5rem] border border-white/10 bg-slate-950/40 p-5">
                <div className="mb-4 flex items-center gap-3">
                  <Users className="h-4 w-4 text-cyan-200" />
                  <p className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-300">League Size</p>
                </div>
                <div className="flex flex-wrap gap-3">
                  {LEAGUE_SIZE_OPTIONS.map((option) => (
                    <OptionButton key={option} active={leagueSize === option} onClick={() => setLeagueSize(option)}>
                      {option} Teams
                    </OptionButton>
                  ))}
                </div>
              </section>

              <section className="rounded-[1.5rem] border border-white/10 bg-slate-950/40 p-5">
                <div className="mb-4 flex items-center gap-3">
                  <Clock3 className="h-4 w-4 text-cyan-200" />
                  <p className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-300">Pick Time Limit</p>
                </div>
                <div className="flex flex-wrap gap-3">
                  {TIMER_OPTIONS.map((option) => (
                    <OptionButton key={option} active={pickTimer === option} onClick={() => setPickTimer(option)}>
                      {option}s
                    </OptionButton>
                  ))}
                </div>
              </section>

              <section className="rounded-[1.5rem] border border-cyan-200/16 bg-cyan-300/[0.055] p-5">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-200">Roster-Fill Rounds</p>
                    <p className="mt-2 max-w-2xl text-sm font-bold leading-6 text-slate-300">
                      Rounds are locked to the roster size: QB, 2 RB, 2 WR, TE, FLEX, K, and 5 bench spots.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-cyan-200/35 bg-slate-950/45 px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-cyan-50">
                    {MOCK_ROUNDS} Rounds
                  </div>
                </div>
              </section>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="overflow-hidden rounded-[2rem] border border-sky-300/16 bg-card/55 shadow-[0_30px_70px_rgba(14,165,233,0.08)]">
            <CardContent className="space-y-5 p-6 md:p-8">
              <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.32em] text-cyan-200">
                <ShieldCheck className="h-4 w-4" />
                Current Mock Rules
              </p>
              <div className="grid gap-3 text-sm font-bold uppercase tracking-[0.14em] text-slate-200/74">
                <p>{leagueSize} teams • snake order • {MOCK_ROUNDS} roster-fill rounds</p>
                <p>{pickTimer}s user pick timer</p>
                <p>Bot picks advance automatically after about two seconds</p>
                <p>No real rosters, league status, trades, or standings are touched</p>
              </div>
            </CardContent>
          </Card>

          <Card className="overflow-hidden rounded-[2rem] border border-sky-300/16 bg-card/55 shadow-[0_30px_70px_rgba(14,165,233,0.08)]">
            <CardContent className="space-y-5 p-6 md:p-8">
              <div className="flex items-center justify-between gap-4">
                <p className="text-[10px] font-black uppercase tracking-[0.32em] text-cyan-200">
                  Real League Drafts
                </p>
                <Button
                  asChild
                  variant="outline"
                  className="h-10 rounded-xl border-white/15 bg-white/[0.05] px-4 text-[10px] font-black uppercase tracking-[0.16em] text-white hover:bg-white/10"
                >
                  <Link to="/leagues">
                    <ClipboardList className="mr-2 h-4 w-4" />
                    Leagues
                  </Link>
                </Button>
              </div>
              {realDrafts.length === 0 ? (
                <p className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 text-sm font-bold text-muted-foreground">
                  No scheduled or live real drafts. Join or create a league first.
                </p>
              ) : (
                <div className="space-y-3">
                  {realDrafts.map((league) => (
                    <Link
                      key={league.id}
                      to={`/league/${league.id}/draft`}
                      className="block rounded-2xl border border-white/10 bg-white/[0.055] p-5 transition hover:-translate-y-0.5 hover:border-cyan-200/40 hover:bg-cyan-300/10 hover:shadow-[0_0_26px_rgba(56,189,248,0.12)]"
                    >
                      <p className="text-lg font-black tracking-tight text-foreground">{league.name}</p>
                      <p className="mt-2 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
                        {formatDraftTime(league.draft?.draft_datetime_utc)}
                      </p>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
