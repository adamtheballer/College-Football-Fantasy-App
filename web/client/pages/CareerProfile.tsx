import { useState } from "react";
import { CalendarDays, Medal, Swords, Trophy, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { ErrorState, SkeletonState } from "@/components/states";
import {
  useCareerEvents,
  useCareerLeagues,
  useCareerProfile,
  useCareerTrophies,
} from "@/hooks/use-leagues";
import type { CareerRecord } from "@/types/career";

type ProfileTab = "overview" | "history" | "leagues" | "trophies";

const formatRecord = (record?: CareerRecord | null) => {
  if (!record) return "0-0";
  return record.ties > 0 ? `${record.wins}-${record.losses}-${record.ties}` : `${record.wins}-${record.losses}`;
};

const formatDate = (value?: string | null) => {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleDateString(undefined, { month: "short", year: "numeric" });
};

const profileInitials = (name?: string | null) =>
  (name ?? "Manager")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "CF";

function StatCard({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <article className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/80 px-4 py-3 shadow-[0_10px_24px_rgba(2,6,23,0.2)]">
      <p className="cfb-micro-label text-cfb-text-muted">{label}</p>
      <p className="mt-1 text-2xl font-black tabular-nums text-cfb-text-primary">{value}</p>
      {detail ? <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.12em] text-cfb-text-secondary">{detail}</p> : null}
    </article>
  );
}

export default function CareerProfile() {
  const profileQuery = useCareerProfile();
  const eventsQuery = useCareerEvents();
  const leaguesQuery = useCareerLeagues();
  const trophiesQuery = useCareerTrophies();
  const [tab, setTab] = useState<ProfileTab>("overview");

  if (profileQuery.isLoading) {
    return <main className="mx-auto w-full max-w-6xl px-4 py-8"><SkeletonState rows={6} /></main>;
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-8">
        <ErrorState title="Unable to load career profile" message="Your league data is safe. Try loading your career résumé again." retryLabel="Try Again" onRetry={() => void profileQuery.refetch()} />
      </main>
    );
  }

  const profile = profileQuery.data;
  const tabs: Array<{ id: ProfileTab; label: string }> = [
    { id: "overview", label: "Overview" },
    { id: "history", label: "History" },
    { id: "leagues", label: "Leagues" },
    { id: "trophies", label: "Trophy Case" },
  ];

  return (
    <main className="relative mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 pb-28 pt-6 sm:px-6 sm:pt-10">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-80 bg-[radial-gradient(circle_at_12%_10%,rgba(59,130,246,0.15),transparent_34%),radial-gradient(circle_at_92%_0%,rgba(234,179,8,0.10),transparent_30%)] blur-3xl" />
      <header className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/92 p-5 shadow-[0_20px_50px_rgba(2,6,23,0.25)] sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl border border-cfb-gold/35 bg-cfb-gold/10 text-xl font-black text-cfb-gold">{profileInitials(profile.display_name)}</div>
            <div className="min-w-0">
              <p className="cfb-micro-label text-cfb-gold">College Fantasy Football</p>
              <h1 className="mt-1 truncate text-3xl font-black italic uppercase text-cfb-text-primary sm:text-4xl">{profile.display_name}</h1>
              <p className="mt-1 text-sm font-medium text-cfb-text-secondary">{profile.username ? `@${profile.username} · ` : ""}Member since {formatDate(profile.member_since)}</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center sm:min-w-[300px]">
            <StatCard label="Career record" value={formatRecord(profile.record)} />
            <StatCard label="Leagues" value={profile.leagues.joined ?? 0} />
            <StatCard label="Titles" value={profile.postseason.championships ?? 0} />
          </div>
        </div>
      </header>

      <nav className="flex overflow-x-auto border-b border-cfb-border-subtle" aria-label="Career profile sections">
        {tabs.map((item) => (
          <button key={item.id} type="button" onClick={() => setTab(item.id)} className={`shrink-0 border-b-2 px-4 py-3 text-[11px] font-black uppercase tracking-[0.15em] transition ${tab === item.id ? "border-cfb-brand text-cfb-text-primary" : "border-transparent text-cfb-text-muted hover:text-cfb-text-secondary"}`}>
            {item.label}
          </button>
        ))}
      </nav>

      {tab === "overview" ? (
        <section className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Win percentage" value={`${((profile.record.win_pct ?? 0) * 100).toFixed(1)}%`} detail={formatRecord(profile.record)} />
            <StatCard label="Fantasy points" value={(profile.scoring.points_for ?? 0).toFixed(1)} detail={`${(profile.scoring.average_points ?? 0).toFixed(1)} per matchup`} />
            <StatCard label="Drafts completed" value={profile.drafts.official_completed ?? 0} detail={`${profile.drafts.mock_completed ?? 0} mock drafts`} />
            <StatCard label="Trades completed" value={profile.trades.completed ?? 0} detail={`${profile.waivers.won ?? 0} waiver claims won`} />
          </div>
          <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
            <section className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/80 p-5">
              <div className="flex items-center gap-2"><Trophy className="h-5 w-5 text-cfb-gold" /><h2 className="text-lg font-black text-cfb-text-primary">Career form</h2></div>
              <dl className="mt-5 grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-3">
                <div><dt className="cfb-micro-label text-cfb-text-muted">High week</dt><dd className="mt-1 text-xl font-black">{profile.scoring.high_week?.toFixed(1) ?? "—"}</dd></div>
                <div><dt className="cfb-micro-label text-cfb-text-muted">Low week</dt><dd className="mt-1 text-xl font-black">{profile.scoring.low_week?.toFixed(1) ?? "—"}</dd></div>
                <div><dt className="cfb-micro-label text-cfb-text-muted">Best streak</dt><dd className="mt-1 text-xl font-black">{profile.streaks.longest_win ?? 0} W</dd></div>
                <div><dt className="cfb-micro-label text-cfb-text-muted">Current streak</dt><dd className="mt-1 text-xl font-black">{profile.streaks.current_win ?? 0} W</dd></div>
                <div><dt className="cfb-micro-label text-cfb-text-muted">Playoff trips</dt><dd className="mt-1 text-xl font-black">{profile.postseason.appearances ?? 0}</dd></div>
                <div><dt className="cfb-micro-label text-cfb-text-muted">Completed matchups</dt><dd className="mt-1 text-xl font-black">{profile.matchups.completed ?? 0}</dd></div>
                <div><dt className="cfb-micro-label text-cfb-text-muted">Regular-season #1</dt><dd className="mt-1 text-xl font-black">{profile.postseason.regular_season_first_place ?? 0}</dd></div>
                <div><dt className="cfb-micro-label text-cfb-text-muted">Rival record</dt><dd className="mt-1 text-xl font-black">{profile.rivalry.wins ?? 0}-{profile.rivalry.losses ?? 0}</dd></div>
              </dl>
            </section>
            <section className="rounded-2xl border border-cfb-gold/25 bg-[linear-gradient(145deg,rgba(234,179,8,0.12),rgba(15,23,42,0.88))] p-5">
              <div className="flex items-center gap-2"><Swords className="h-5 w-5 text-cfb-gold" /><h2 className="text-lg font-black text-cfb-text-primary">Rival Week</h2></div>
              <p className="mt-3 text-sm leading-6 text-cfb-text-secondary">Choose one league rival in League Settings. Rivalry matchups track a real record only—they never change scores, odds, or standings.</p>
              <Link to="/leagues" className="mt-5 inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.14em] text-cfb-gold hover:text-cfb-text-primary"><Users className="h-4 w-4" /> Open leagues</Link>
            </section>
          </div>
        </section>
      ) : null}

      {tab === "history" ? (
        <section className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/80">
          <div className="border-b border-cfb-border-subtle px-5 py-4"><h2 className="text-lg font-black text-cfb-text-primary">Career history</h2></div>
          {eventsQuery.isLoading ? <div className="p-5"><SkeletonState rows={4} /></div> : (eventsQuery.data?.data ?? []).length ? <ol className="divide-y divide-cfb-border-subtle">{eventsQuery.data?.data.map((event) => <li key={event.id} className="flex gap-4 px-5 py-4"><CalendarDays className="mt-0.5 h-4 w-4 shrink-0 text-cfb-brand" /><div><p className="text-sm font-bold text-cfb-text-primary">{event.title}</p><p className="mt-1 text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">{event.season ?? "Career"}{event.week ? ` · Week ${event.week}` : ""} · {formatDate(event.occurred_at)}</p></div></li>)}</ol> : <p className="p-5 text-sm text-cfb-text-secondary">Completed drafts, finalized matchups, trades, and rivalry selections will appear here as they happen.</p>}
        </section>
      ) : null}

      {tab === "leagues" ? (
        <section className="overflow-hidden rounded-2xl border border-cfb-border-subtle bg-cfb-surface/80">
          <div className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-cfb-border-subtle px-5 py-3 cfb-micro-label text-cfb-text-muted"><span>League</span><span>Record</span><span>Points</span></div>
          {(leaguesQuery.data ?? []).length ? leaguesQuery.data?.map((league) => <Link key={league.league_id} to={`/league/${league.league_id}/roster`} className="grid grid-cols-[1fr_auto_auto] gap-3 border-b border-cfb-border-subtle px-5 py-4 last:border-0 hover:bg-white/[0.03]"><span className="min-w-0"><span className="block truncate text-sm font-black text-cfb-text-primary">{league.name}</span><span className="mt-1 block text-[10px] font-bold uppercase tracking-[0.12em] text-cfb-text-muted">{league.season} · {league.status}</span>{league.rival_team_name ? <span className="mt-1 block text-[10px] font-bold text-cfb-gold">Rival: {league.rival_team_name}</span> : null}</span><span className="text-sm font-black tabular-nums text-cfb-text-primary">{formatRecord(league.record)}</span><span className="text-sm font-black tabular-nums text-cfb-brand">{league.points_for.toFixed(1)}</span></Link>) : <p className="p-5 text-sm text-cfb-text-secondary">Your completed and active leagues will appear here.</p>}
        </section>
      ) : null}

      {tab === "trophies" ? (
        <section className="grid gap-3 sm:grid-cols-2">
          {(trophiesQuery.data ?? []).length ? trophiesQuery.data?.map((trophy) => <article key={trophy.key} className="rounded-2xl border border-cfb-gold/25 bg-cfb-surface/80 p-5"><Medal className="h-6 w-6 text-cfb-gold" /><h2 className="mt-4 text-lg font-black text-cfb-text-primary">{trophy.title}</h2><p className="mt-1 text-sm text-cfb-text-secondary">{trophy.season ?? "Career"}{trophy.subtitle ? ` · ${trophy.subtitle}` : ""}</p></article>) : <article className="rounded-2xl border border-dashed border-cfb-border-subtle bg-cfb-surface/60 p-5 text-sm text-cfb-text-secondary">Trophies appear only after verified postseason results are finalized.</article>}
        </section>
      ) : null}
    </main>
  );
}
