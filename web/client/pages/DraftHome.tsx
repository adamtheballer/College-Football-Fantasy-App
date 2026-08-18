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
      "h-11 min-w-0 rounded-xl border px-2 text-[9px] font-black uppercase tracking-[0.14em] transition sm:h-12 sm:rounded-2xl sm:px-5 sm:text-[11px] sm:tracking-[0.18em]",
      "hover:-translate-y-0.5 hover:border-cfb-brand/45 hover:bg-cfb-brand/10 hover:shadow-[0_0_26px_hsl(var(--brand-primary)/0.16)]",
      active
        ? "border-cfb-brand/70 bg-cfb-brand/20 text-blue-50 shadow-[0_0_34px_hsl(var(--brand-primary)/0.22)]"
        : "border-cfb-border-subtle bg-cfb-surface/70 text-cfb-text-secondary"
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
      league.status === "draft_pre_draft" ||
      league.status === "draft_scheduled" ||
      ["pre_draft", "on_clock", "transition", "live", "scheduled"].includes(league.draft?.status ?? "")
  );

  return (
    <div className="relative mx-auto max-w-[1320px] space-y-4 px-4 py-5 pb-24 sm:space-y-6 sm:py-7 md:px-8">
      <div className="pointer-events-none absolute left-0 top-6 h-52 w-52 rounded-full bg-sky-400/12 blur-[82px] sm:top-10 sm:h-72 sm:w-72 sm:blur-[92px]" />
      <div className="pointer-events-none absolute right-0 top-32 h-56 w-56 rounded-full bg-blue-500/10 blur-[82px] sm:top-40 sm:h-80 sm:w-80 sm:blur-[100px]" />

      <header className="relative flex flex-col gap-3 sm:gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1.5 sm:space-y-3">
          <p className="cfb-micro-label text-cfb-brand">
            Draft Center
          </p>
          <h1 className="cfb-display-title text-4xl italic leading-none sm:text-5xl md:text-7xl">
            Draft
          </h1>
          <p className="max-w-3xl text-sm font-semibold leading-6 text-cfb-text-secondary sm:hidden">
            Start a private mock or enter a league draft.
          </p>
          <p className="hidden max-w-3xl text-base font-semibold leading-7 text-cfb-text-secondary sm:block">
            Practice in a local-only single-player mock, preview league drafts, and enter the real draft room only when a league draft is ready.
          </p>
        </div>
        <Button
          asChild
          className="h-12 w-full rounded-xl bg-gradient-to-r from-cfb-cyan to-cfb-brand px-5 text-[10px] font-black uppercase tracking-[0.16em] text-slate-950 shadow-[0_18px_42px_hsl(var(--brand-primary)/0.22)] hover:brightness-110 sm:h-14 sm:w-fit sm:rounded-2xl sm:px-7 sm:text-[11px] sm:tracking-[0.2em]"
        >
          <Link to={mockDraftUrl}>
            <Bot className="mr-3 h-5 w-5" />
            Start Single-Player Mock
          </Link>
        </Button>
      </header>

      <div className="relative grid gap-4 xl:grid-cols-[1.15fr_0.85fr] xl:gap-6">
        <Card className="order-2 cfb-playbook-pattern overflow-hidden rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/90 shadow-[0_0_54px_hsl(var(--brand-primary)/0.1)] sm:rounded-[2rem] xl:order-1">
          <CardContent className="space-y-4 p-4 sm:space-y-6 sm:p-6 md:p-8">
            <div className="flex items-start gap-3 sm:gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-cfb-brand/30 bg-cfb-brand/15 text-blue-100 shadow-[0_0_20px_hsl(var(--brand-primary)/0.16)] sm:h-12 sm:w-12 sm:rounded-2xl">
                <Trophy className="h-5 w-5" />
              </div>
              <div>
                <p className="cfb-micro-label text-cfb-brand">Mock Draft Setup</p>
                <h2 className="mt-1 text-xl font-black italic tracking-tight text-cfb-text-primary sm:mt-2 sm:text-2xl">Set up your room</h2>
                <p className="mt-1 text-xs font-semibold leading-5 text-cfb-text-secondary sm:hidden">
                  Choose your league size and pick clock.
                </p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.14em] text-cyan-100/75 sm:hidden">
                  Private • browser-only • no league changes
                </p>
                <p className="mt-2 hidden max-w-2xl text-sm font-semibold leading-6 text-cfb-text-secondary sm:block">
                  These settings apply to the next new single-player mock. Mock drafts run in this browser only and are not saved to the backend.
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:gap-5">
              <div className="grid gap-3 sm:grid-cols-2 sm:gap-5">
                <section className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-3 sm:rounded-[1.5rem] sm:p-5">
                  <div className="mb-2 flex items-center gap-2 sm:mb-4 sm:gap-3">
                  <Users className="h-4 w-4 text-cyan-200" />
                    <p className="text-[9px] font-black uppercase tracking-[0.2em] text-slate-300 sm:text-[10px] sm:tracking-[0.24em]">League Size</p>
                  </div>
                  <div className="grid grid-cols-3 gap-2 sm:gap-3">
                    {LEAGUE_SIZE_OPTIONS.map((option) => (
                      <OptionButton key={option} active={leagueSize === option} onClick={() => setLeagueSize(option)}>
                        {option} Teams
                      </OptionButton>
                    ))}
                  </div>
                </section>

                <section className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-3 sm:rounded-[1.5rem] sm:p-5">
                  <div className="mb-2 flex items-center gap-2 sm:mb-4 sm:gap-3">
                  <Clock3 className="h-4 w-4 text-cyan-200" />
                    <p className="text-[9px] font-black uppercase tracking-[0.2em] text-slate-300 sm:text-[10px] sm:tracking-[0.24em]">Pick Clock</p>
                  </div>
                  <div className="grid grid-cols-3 gap-2 sm:gap-3">
                    {TIMER_OPTIONS.map((option) => (
                      <OptionButton key={option} active={pickTimer === option} onClick={() => setPickTimer(option)}>
                        {option}s
                      </OptionButton>
                    ))}
                  </div>
                </section>
              </div>

              <section className="rounded-xl border border-cfb-brand/25 bg-cfb-brand/[0.07] p-3 sm:rounded-[1.5rem] sm:p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[9px] font-black uppercase tracking-[0.2em] text-cyan-200 sm:text-[10px] sm:tracking-[0.24em]">Roster Fill</p>
                    <p className="mt-1 text-xs font-bold leading-5 text-slate-300 sm:text-sm">
                      QB, 2 RB, 2 WR, TE, FLEX, K, and bench.
                    </p>
                  </div>
                  <div className="shrink-0 rounded-xl border border-cyan-200/35 bg-slate-950/45 px-3 py-2 text-[9px] font-black uppercase tracking-[0.14em] text-cyan-50 sm:rounded-2xl sm:px-5 sm:py-3 sm:text-[11px] sm:tracking-[0.18em]">
                    {MOCK_ROUNDS} Rounds
                  </div>
                </div>
              </section>
            </div>
          </CardContent>
        </Card>

        <div className="order-1 space-y-4 xl:order-2 xl:space-y-6">
          <Card className="overflow-hidden rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/85 shadow-[0_24px_52px_rgba(2,6,23,0.2)] sm:rounded-[2rem]">
            <CardContent className="space-y-3 p-4 sm:space-y-5 sm:p-6 md:p-8">
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
                <p className="rounded-xl border border-white/10 bg-white/[0.04] p-3 text-xs font-bold leading-5 text-muted-foreground sm:rounded-2xl sm:p-5 sm:text-sm">
                  No scheduled or live real drafts. Join or create a league first.
                </p>
              ) : (
                <div className="space-y-2 sm:space-y-3">
                  {realDrafts.map((league) => (
                    <Link
                      key={league.id}
                      to={`/league/${league.id}/draft`}
                      className="block rounded-xl border border-white/10 bg-white/[0.055] p-3 transition hover:-translate-y-0.5 hover:border-cyan-200/40 hover:bg-cyan-300/10 hover:shadow-[0_0_26px_rgba(56,189,248,0.12)] sm:rounded-2xl sm:p-5"
                    >
                      <p className="text-base font-black italic tracking-tight text-foreground sm:text-lg">{league.name}</p>
                      <p className="mt-1 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground sm:mt-2 sm:text-[10px] sm:tracking-[0.2em]">
                        {formatDraftTime(league.draft?.draft_datetime_utc)}
                      </p>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="hidden overflow-hidden rounded-[2rem] border border-cfb-border-subtle bg-cfb-surface-raised/85 shadow-[0_30px_70px_rgba(2,6,23,0.22)] sm:block">
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
        </div>
      </div>
    </div>
  );
}
