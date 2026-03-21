import type { ComponentType } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Calendar, ChevronRight, Lock, Globe2, Users, Settings2, Activity, ShieldCheck, ListOrdered } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { useLeagueDetail, useLeagueWorkspace } from "@/hooks/use-leagues";

const SummaryCard = ({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string }>;
}) => (
  <Card className="bg-card/40 border-white/10 rounded-[2rem]">
    <CardContent className="p-6 flex items-center justify-between gap-4">
      <div className="space-y-1">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
          {label}
        </p>
        <p className="text-2xl font-black italic text-foreground">{value}</p>
      </div>
      <Icon className="w-6 h-6 text-primary" />
    </CardContent>
  </Card>
);

export default function LeagueDetail() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const parsedLeagueId = leagueId && /^\d+$/.test(leagueId) ? Number(leagueId) : undefined;
  const { data: league, isLoading, error } = useLeagueDetail(parsedLeagueId);
  const { data: workspace, error: workspaceError } = useLeagueWorkspace(parsedLeagueId);

  if (!parsedLeagueId) {
    return (
      <div className="max-w-4xl mx-auto py-16">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardContent className="p-12 text-center">
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
              Invalid league ID.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto py-16">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardContent className="p-12 text-center">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
              Loading league...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!league || error) {
    return (
      <div className="max-w-4xl mx-auto py-16">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardContent className="p-12 text-center space-y-4">
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
              Unable to load league metadata.
            </p>
            <Button
              variant="outline"
              className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate("/leagues")}
            >
              Back to Leagues
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const membership = league.members.find((member) => member.user_id === user?.id) || null;
  const isCommissioner = league.commissioner_user_id === user?.id;
  const draftDate = league.draft?.draft_datetime_utc
    ? new Date(league.draft.draft_datetime_utc).toLocaleString()
    : "Draft not scheduled";
  const workspaceActions = Array.isArray(workspace?.allowed_actions)
    ? workspace.allowed_actions
    : workspace?.allowed_actions
      ? Object.entries(workspace.allowed_actions)
          .filter(([, allowed]) => Boolean(allowed))
          .map(([action]) => action)
      : [];

  return (
    <div className="max-w-6xl mx-auto space-y-10 animate-in fade-in duration-700 pb-16">
      <div className="flex flex-col gap-6 pt-12">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-3">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">
              Live League Hub
            </p>
            <h1 className="text-6xl font-black italic uppercase tracking-tight text-foreground">
              {league.name}
            </h1>
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">
              Season {league.season_year} • {league.status.replace(/_/g, " ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate(`/league/${league.id}/lobby`)}
            >
              Draft Lobby
              <ChevronRight className="ml-2 h-3 w-3" />
            </Button>
            <Button
              variant="outline"
              className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate("/leagues")}
            >
              Back to Leagues
            </Button>
          </div>
        </div>
        <p className="max-w-3xl text-muted-foreground text-base leading-7">
          This hub renders live backend league metadata and now consumes the canonical workspace contract for owned team context, roster state, standings, and allowed actions.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
        <SummaryCard label="Members" value={`${league.members.length}/${league.max_teams}`} icon={Users} />
        <SummaryCard label="Draft" value={draftDate} icon={Calendar} />
        <SummaryCard
          label="Visibility"
          value={league.is_private ? "Private" : "Public"}
          icon={league.is_private ? Lock : Globe2}
        />
        <SummaryCard
          label="Your Role"
          value={membership ? membership.role : "Member pending"}
          icon={Activity}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.3fr_1fr] gap-6">
        <Card className="bg-card/40 border border-white/10 rounded-[2.5rem] overflow-hidden">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
              Overview
            </CardTitle>
          </CardHeader>
          <CardContent className="p-8 space-y-6">
            <div className="space-y-2">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Description
              </p>
              <p className="text-sm text-foreground/90 leading-7">
                {league.description?.trim() || "No league description provided yet."}
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Commissioner
                </p>
                <p className="text-sm font-bold text-foreground">
                  User {league.commissioner_user_id ?? "Unknown"}
                </p>
                <p className="text-[11px] text-muted-foreground/70">
                  {isCommissioner ? "You manage this league." : "Commissioner-only actions stay scoped to the commissioner."}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Invite Code
                </p>
                <p className="text-sm font-bold text-foreground tracking-[0.18em]">
                  {league.invite_code || "No active code"}
                </p>
                <p className="text-[11px] text-muted-foreground/70">
                  Invite management stays in the live backend flow.
                </p>
              </div>
            </div>
            {workspace ? (
              <div className="rounded-[2rem] border border-emerald-500/20 bg-emerald-500/10 p-6 space-y-3">
                <p className="text-[10px] font-black uppercase tracking-[0.24em] text-emerald-300">
                  Workspace Connected
                </p>
                <p className="text-sm text-emerald-50/90 leading-7">
                  This league now has a canonical workspace payload. The React hub is reading your membership, owned team, roster snapshot, standings, and allowed actions from one backend response.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px] uppercase tracking-[0.14em]">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    Owned Team: {workspace.owned_team?.name || "Not assigned"}
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    Roster Entries: {workspace.roster.length}
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    Standings Rows: {workspace.standings_summary.length}
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-[2rem] border border-amber-500/20 bg-amber-500/10 p-6 space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.24em] text-amber-300">
                  Workspace Unavailable
                </p>
                <p className="text-sm text-amber-50/90 leading-7">
                  The canonical workspace contract is live, but this league hub could not load it right now. Check your permissions or refresh the page to retry.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="bg-card/40 border border-white/10 rounded-[2.5rem] overflow-hidden">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.28em] text-primary">
                <Settings2 className="w-4 h-4" />
                League Settings
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Waiver Type
                </p>
                <p className="mt-2 text-sm font-bold text-foreground uppercase">
                  {league.settings.waiver_type}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Trade Review
                </p>
                <p className="mt-2 text-sm font-bold text-foreground uppercase">
                  {league.settings.trade_review_type}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Playoff Teams
                </p>
                <p className="mt-2 text-sm font-bold text-foreground">
                  {league.settings.playoff_teams}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border border-white/10 rounded-[2.5rem] overflow-hidden">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
                Members
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {league.members.length === 0 ? (
                <div className="p-6 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  No members found.
                </div>
              ) : (
                league.members.map((member) => (
                  <div
                    key={member.id}
                    className="flex items-center justify-between px-6 py-4 border-b border-white/10 last:border-b-0"
                  >
                    <div>
                      <p className="text-sm font-black text-foreground uppercase tracking-[0.12em]">
                        User {member.user_id}
                      </p>
                      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground/60">
                        Joined {new Date(member.joined_at).toLocaleDateString()}
                      </p>
                    </div>
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                      {member.role}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="bg-card/40 border border-white/10 rounded-[2.5rem] overflow-hidden">
        <CardHeader className="border-b border-white/10">
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
            Supported Actions
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          {workspace && (
            <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_1fr_1fr] gap-6">
              <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5 space-y-4">
                <div className="flex items-center gap-3">
                  <ShieldCheck className="h-4 w-4 text-primary" />
                  <p className="text-[10px] font-black uppercase tracking-[0.24em] text-primary">
                    Team Snapshot
                  </p>
                </div>
                <p className="text-sm font-black uppercase tracking-[0.12em] text-foreground">
                  {workspace.owned_team?.name || "No team assigned"}
                </p>
                {workspace.roster.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground/70">
                    Your team does not have roster entries yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {workspace.roster.slice(0, 6).map((entry) => (
                      <div
                        key={entry.id}
                        className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/10 px-4 py-3"
                      >
                        <div>
                          <p className="text-[11px] font-black uppercase tracking-[0.12em] text-foreground">
                            {entry.player_name || `Player ${entry.player_id}`}
                          </p>
                          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground/60">
                            {entry.player_position || "Unknown"} · {entry.player_school || "School pending"}
                          </p>
                        </div>
                        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                          {entry.slot || "Bench"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5 space-y-4">
                <div className="flex items-center gap-3">
                  <ListOrdered className="h-4 w-4 text-primary" />
                  <p className="text-[10px] font-black uppercase tracking-[0.24em] text-primary">
                    Standings Snapshot
                  </p>
                </div>
                {workspace.standings_summary.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground/70">
                    No standings rows are available yet.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {workspace.standings_summary.slice(0, 5).map((row) => (
                      <div
                        key={row.team_id}
                        className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/10 px-4 py-3"
                      >
                        <div>
                          <p className="text-[11px] font-black uppercase tracking-[0.12em] text-foreground">
                            {row.team_name}
                          </p>
                          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground/60">
                            {row.wins ?? 0}-{row.losses ?? 0}-{row.ties ?? 0}
                          </p>
                        </div>
                        <span className="text-sm font-black italic text-primary">
                          #{row.rank ?? "-"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-[2rem] border border-white/10 bg-white/5 p-5 space-y-4">
                <p className="text-[10px] font-black uppercase tracking-[0.24em] text-primary">
                  Allowed Actions
                </p>
                <div className="flex flex-wrap gap-2">
                  {workspaceActions.map((action) => (
                    <span
                      key={action}
                      className="rounded-full border border-white/10 bg-black/10 px-3 py-2 text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground"
                    >
                      {action.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <Button asChild className="rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]">
              <Link to={`/league/${league.id}/lobby`}>
                Open Draft Lobby
              </Link>
            </Button>
            <Button asChild variant="outline" className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]">
              <Link to="/settings">
                Notification Settings
              </Link>
            </Button>
            <Button asChild variant="outline" className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]">
              <Link to="/rosters">
                Choose Another League
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
