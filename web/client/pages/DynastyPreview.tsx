import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import {
  dynastyApi,
  type DynastyAsset,
  type DynastyFinish,
  type DynastyState,
} from "@/lib/dynasty";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const panel = "rounded-xl border border-border bg-card p-5 space-y-4";
const field = "grid gap-1 text-sm";
const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Request failed. Refresh and retry.";

export default function DynastyPreview() {
  const { user } = useAuth();
  const cache = useQueryClient();
  const [params] = useSearchParams();
  const [leagueId, setLeagueId] = useState<number | null>(() => {
    const id = Number(params.get("league"));
    return Number.isInteger(id) && id > 0 ? id : null;
  });
  const [notice, setNotice] = useState("");
  const capability = useQuery({
    queryKey: ["dynasty", "capability"],
    queryFn: dynastyApi.capability,
    retry: false,
  });
  const list = useQuery({
    queryKey: ["dynasty", "list"],
    queryFn: dynastyApi.list,
    enabled: capability.data?.enabled === true,
  });
  const league = useQuery({
    queryKey: ["dynasty", leagueId],
    queryFn: () => dynastyApi.detail(leagueId!),
    enabled: !!leagueId && capability.data?.enabled === true,
    refetchInterval: 5000,
  });
  const mutation = useMutation({
    mutationFn: (action: () => Promise<DynastyState>) => action(),
    retry: false,
    onSuccess: async (state) => {
      setLeagueId(state.league_id);
      setNotice("Saved.");
      cache.setQueryData(["dynasty", state.league_id], state);
      await cache.invalidateQueries({ queryKey: ["dynasty"] });
    },
    onError: () => setNotice(""),
  });
  useEffect(() => {
    if (!leagueId && list.data?.data.length)
      setLeagueId(list.data.data[0].league_id);
  }, [list.data, leagueId]);
  const run = (fn: () => Promise<DynastyState>) => {
    setNotice("");
    mutation.mutate(fn);
  };
  const state = league.data;
  const mine = state?.teams.find((t) => t.owner_user_id === user?.id);
  const commissioner = state?.commissioner_user_id === user?.id;
  const teamName = (id: number) =>
    state?.teams.find((t) => t.id === id)?.name ?? `Team ${id}`;
  const busy = mutation.isPending;

  if (capability.isPending)
    return <p role="status">Loading dynasty preview…</p>;
  if (capability.error)
    return (
      <section className={panel}>
        <h1 className="text-2xl font-bold">Dynasty preview unavailable</h1>
        <p>
          {capability.error instanceof ApiError &&
          capability.error.status === 404
            ? "This preview is disabled in this environment."
            : errorMessage(capability.error)}
        </p>
        <Button onClick={() => capability.refetch()}>Retry</Button>
      </section>
    );

  return (
    <main className="mx-auto max-w-6xl space-y-6 py-6">
      <header>
        <p className="text-sm text-muted-foreground">2027 preview</p>
        <h1 className="text-3xl font-bold">Build your dynasty</h1>
        <p>
          Keep your roster. Draft incoming freshmen each offseason. Trade
          players and future picks.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Draft and roster preview. Season results require commissioner review.
          Values are provisional.
        </p>
      </header>
      {mutation.error && (
        <p role="alert" className="text-destructive">
          {errorMessage(mutation.error)}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {list.error && (
        <p role="alert">
          {errorMessage(list.error)}{" "}
          <Button onClick={() => list.refetch()}>Retry leagues</Button>
        </p>
      )}
      <div className="grid gap-6 md:grid-cols-2">
        <form
          className={panel}
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            run(() =>
              dynastyApi.create({
                name: String(f.get("name")),
                season: Number(f.get("season")),
                team_count: Number(f.get("teams")),
                roster_limit: Number(f.get("roster")),
                startup_rounds: Number(f.get("startup")),
                freshman_rounds: Number(f.get("freshman")),
                future_pick_years: Number(f.get("horizon")),
              }),
            );
          }}
        >
          <h2 className="text-xl font-semibold">Create a dynasty league</h2>
          <label className={field}>
            League name
            <Input name="name" required minLength={3} maxLength={80} />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className={field}>
              First season
              <Input
                name="season"
                type="number"
                min={2027}
                max={2097}
                defaultValue={2027}
                required
              />
            </label>
            <label className={field}>
              Teams
              <Input name="teams" type="number" min={2} max={24} required />
            </label>
            <label className={field}>
              Roster limit
              <Input name="roster" type="number" min={2} max={100} required />
            </label>
            <label className={field}>
              Startup rounds
              <Input name="startup" type="number" min={1} max={100} required />
            </label>
            <label className={field}>
              Freshman rounds
              <Input name="freshman" type="number" min={1} max={20} required />
            </label>
            <label className={field}>
              Future pick years
              <Input
                name="horizon"
                type="number"
                min={1}
                max={3}
                defaultValue={2}
                required
              />
            </label>
          </div>
          <p className="text-sm text-muted-foreground">
            Startup: randomized snake. Annual draft: snake, non-playoff teams
            first by worst regular-season record, then reverse playoff finish.
          </p>
          <Button disabled={busy}>Create preview league</Button>
        </form>
        <form
          className={panel}
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            run(() =>
              dynastyApi.join(String(f.get("code")), String(f.get("team"))),
            );
          }}
        >
          <h2 className="text-xl font-semibold">Join a dynasty league</h2>
          <label className={field}>
            Invite code
            <Input name="code" required maxLength={30} />
          </label>
          <label className={field}>
            Team name
            <Input name="team" required maxLength={80} />
          </label>
          <Button disabled={busy}>Join preview league</Button>
          {list.isPending ? (
            <p role="status">Loading leagues…</p>
          ) : (
            <label className={field}>
              Your dynasty leagues
              <select
                className="rounded border bg-background p-2"
                value={leagueId ?? ""}
                onChange={(e) => setLeagueId(Number(e.target.value))}
              >
                <option value="" disabled>
                  Select a league
                </option>
                {list.data?.data.map((l) => (
                  <option key={l.league_id} value={l.league_id}>
                    {l.name} · {l.current_season}
                  </option>
                ))}
              </select>
            </label>
          )}
          {list.data?.data.length === 0 && <p>No dynasty leagues yet.</p>}
        </form>
      </div>
      {league.isFetching && !state && <p role="status">Loading league…</p>}
      {league.error && (
        <p role="alert">
          {errorMessage(league.error)}{" "}
          <Button onClick={() => league.refetch()}>Retry league</Button>
        </p>
      )}
      {state && (
        <>
          <section className={panel}>
            <h2 className="text-2xl font-semibold">
              {state.name} · {state.current_season}
            </h2>
            <p>
              {state.draft_kind === "startup"
                ? "Startup draft"
                : "Incoming freshman draft"}{" "}
              · {state.status} · {state.pick_cursor} selections made
            </p>
            {state.invite_code && (
              <p>
                Invite code: <code>{state.invite_code}</code>
              </p>
            )}
            {state.order.length > 0 && (
              <p>Round one: {state.order.map(teamName).join(" → ")}</p>
            )}
            <Button asChild>
              <Link to={`/labs/dynasty/${state.league_id}/draft`}>
                Enter draft room
              </Link>
            </Button>
            <p className="text-sm text-muted-foreground">
              Fill all teams and make enough roster space before starting. Every
              player needs reviewed eligibility for this season.
            </p>
          </section>
          <section className={panel}>
            <h2 className="text-xl font-semibold">Persistent rosters</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {state.teams.map((t) => (
                <div key={t.id}>
                  <h3 className="font-semibold">
                    {t.name} ·{" "}
                    {state.rosters.filter((r) => r.team_id === t.id).length}/
                    {state.roster_limit}
                  </h3>
                  <ul>
                    {state.rosters
                      .filter((r) => r.team_id === t.id)
                      .map((r) => (
                        <li
                          key={r.id}
                          className="flex items-center justify-between gap-2 border-b py-2"
                        >
                          <span>
                            {r.name} · {r.position}
                            <span className="block text-xs text-muted-foreground">
                              {r.value?.academic_class ?? "Class unreviewed"} ·
                              Age {r.value?.age ?? "unknown"} · Dynasty{" "}
                              {r.value?.estimate ?? "unrated"}
                            </span>
                          </span>
                          {t.id === mine?.id && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy || state.status === "closed"}
                              onClick={() => {
                                if (
                                  window.confirm(
                                    `Drop ${r.name} from your dynasty roster?`,
                                  )
                                )
                                  run(() =>
                                    dynastyApi.drop(state.league_id, r.id),
                                  );
                              }}
                            >
                              Drop
                            </Button>
                          )}
                        </li>
                      ))}
                  </ul>
                </div>
              ))}
            </div>
            {state.departures.length > 0 && (
              <p>
                Recorded departures:{" "}
                {state.departures
                  .map((d) => `Player ${d.player_id}: ${d.reason}`)
                  .join("; ")}
              </p>
            )}
          </section>
          <section className={panel}>
            <h2 className="text-xl font-semibold">Draft pick assets</h2>
            <div className="grid gap-2 md:grid-cols-3">
              {Array.from(new Set(state.picks.map((p) => p.season))).map(
                (year) => (
                  <div key={year}>
                    <h3 className="font-semibold">{year}</h3>
                    <ul className="text-sm">
                      {state.picks
                        .filter(
                          (p) =>
                            p.season === year && p.owner_team_id === mine?.id,
                        )
                        .map((p) => (
                          <li key={p.id}>
                            Round {p.round_number} ·{" "}
                            {teamName(p.original_team_id)}
                            {p.overall_pick
                              ? ` · Pick ${p.overall_pick}`
                              : " · Order pending"}
                            {p.player_id ? " · Used" : ""}
                          </li>
                        ))}
                    </ul>
                  </div>
                ),
              )}
            </div>
          </section>
          {mine && (
            <TradePanel
              key={`trade:${state.league_id}:${state.current_season}`}
              state={state}
              mine={mine.id}
              busy={busy}
              run={run}
            />
          )}
          {commissioner && (
            <SeasonPanel
              key={`season:${state.league_id}:${state.current_season}`}
              state={state}
              busy={busy}
              run={run}
            />
          )}
        </>
      )}
    </main>
  );
}

function TradePanel({
  state,
  mine,
  busy,
  run,
}: {
  state: DynastyState;
  mine: number;
  busy: boolean;
  run: (f: () => Promise<DynastyState>) => void;
}) {
  const [other, setOther] = useState(
    state.teams.find((t) => t.id !== mine)?.id ?? 0,
  );
  const [give, setGive] = useState<DynastyAsset[]>([]);
  const [receive, setReceive] = useState<DynastyAsset[]>([]);
  useEffect(() => {
    if (!state.teams.some((t) => t.id === other && t.id !== mine)) {
      setOther(state.teams.find((t) => t.id !== mine)?.id ?? 0);
      setReceive([]);
    }
  }, [state.teams, mine, other]);
  const teamName = (id: number) =>
    state.teams.find((t) => t.id === id)?.name ?? `Team ${id}`;
  const assetName = (a: DynastyAsset) =>
    a.kind === "player"
      ? (state.rosters.find((r) => r.player_id === a.id)?.name ??
        `Player ${a.id}`)
      : (() => {
          const p = state.picks.find((p) => p.id === a.id);
          return p
            ? `${p.season} round ${p.round_number} (${teamName(p.original_team_id)})`
            : `Pick ${a.id}`;
        })();
  const options = (tid: number): DynastyAsset[] => [
    ...state.rosters
      .filter((r) => r.team_id === tid)
      .map((r) => ({ kind: "player" as const, id: r.player_id })),
    ...state.picks
      .filter((p) => p.owner_team_id === tid && p.player_id === null)
      .map((p) => ({ kind: "pick" as const, id: p.id })),
  ];
  const choices = (
    tid: number,
    selected: DynastyAsset[],
    set: (a: DynastyAsset[]) => void,
  ) =>
    options(tid).map((a) => (
      <label key={`${a.kind}:${a.id}`} className="flex gap-2 py-1 text-sm">
        <input
          type="checkbox"
          disabled={busy || state.status === "closed"}
          checked={selected.some((s) => s.kind === a.kind && s.id === a.id)}
          onChange={(e) =>
            set(
              e.target.checked
                ? [...selected, a]
                : selected.filter((s) => s.kind !== a.kind || s.id !== a.id),
            )
          }
        />
        {assetName(a)}
      </label>
    ));
  return (
    <section className={panel}>
      <h2 className="text-xl font-semibold">Trade players and picks</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(() =>
            dynastyApi.trade(state.league_id, mine, other, give, receive),
          );
          setGive([]);
          setReceive([]);
        }}
      >
        <label className={field}>
          Trade partner
          <select
            className="rounded border bg-background p-2"
            value={other}
            onChange={(e) => {
              setOther(Number(e.target.value));
              setReceive([]);
            }}
          >
            {state.teams
              .filter((t) => t.id !== mine)
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
          </select>
        </label>
        <div className="my-4 grid gap-4 md:grid-cols-2">
          <fieldset>
            <legend>You give</legend>
            {choices(mine, give, setGive)}
          </fieldset>
          <fieldset>
            <legend>You receive</legend>
            {choices(other, receive, setReceive)}
          </fieldset>
        </div>
        <Button
          disabled={
            busy ||
            !other ||
            !give.length ||
            !receive.length ||
            give.length > 20 ||
            receive.length > 20 ||
            state.status === "closed"
          }
        >
          Propose trade
        </Button>
      </form>
      <ul className="space-y-3">
        {state.trades.map((t) => (
          <li key={t.id} className="rounded border p-3">
            <p>
              {teamName(t.from_team_id)} → {teamName(t.to_team_id)} · {t.status}
            </p>
            <p className="text-sm">
              {t.assets_json
                .map((a) => `${teamName(a.from_team_id)} gives ${assetName(a)}`)
                .join("; ")}
            </p>
            {t.status === "pending" && (
              <div className="mt-2 flex gap-2">
                {t.to_team_id === mine && (
                  <>
                    <Button
                      disabled={busy || state.status === "closed"}
                      onClick={() =>
                        run(() =>
                          dynastyApi.settle(state.league_id, t.id, "accept"),
                        )
                      }
                    >
                      Accept trade #{t.id}
                    </Button>
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() =>
                        run(() =>
                          dynastyApi.settle(state.league_id, t.id, "reject"),
                        )
                      }
                    >
                      Reject
                    </Button>
                  </>
                )}
                {t.from_team_id === mine && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      run(() =>
                        dynastyApi.settle(state.league_id, t.id, "cancel"),
                      )
                    }
                  >
                    Cancel trade #{t.id}
                  </Button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function SeasonPanel({
  state,
  busy,
  run,
}: {
  state: DynastyState;
  busy: boolean;
  run: (f: () => Promise<DynastyState>) => void;
}) {
  const [history, setHistory] = useState<number | null>(null);
  const historical = useQuery({
    queryKey: ["dynasty", state.league_id, "history", history],
    queryFn: () => dynastyApi.history(state.league_id, history!),
    enabled: history !== null,
  });
  return (
    <section className={panel}>
      <h2 className="text-xl font-semibold">Commissioner season review</h2>
      <p className="text-sm">
        Enter final regular-season records and playoff finishes after the season
        ends. Leave playoff finish blank for non-playoff teams. Champion = 1.
        Results and rosters are frozen when closed.
      </p>
      {state.status === "complete" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const results: DynastyFinish[] = state.teams.map((t) => ({
              team_id: t.id,
              wins: Number(f.get(`wins-${t.id}`)),
              losses: Number(f.get(`losses-${t.id}`)),
              ties: Number(f.get(`ties-${t.id}`)),
              points_for: Number(f.get(`points-${t.id}`)),
              playoff_finish: f.get(`finish-${t.id}`)
                ? Number(f.get(`finish-${t.id}`))
                : null,
            }));
            if (window.confirm("Close this season and freeze these results?"))
              run(() => dynastyApi.close(state.league_id, results));
          }}
        >
          <div className="space-y-4">
            {state.teams.map((t) => (
              <fieldset
                key={t.id}
                className="grid grid-cols-2 gap-2 md:grid-cols-5"
              >
                <legend className="mb-2 font-semibold">{t.name}</legend>
                {["wins", "losses", "ties", "points", "finish"].map((key) => (
                  <label key={key} className={field}>
                    {key === "points"
                      ? "Points for"
                      : key === "finish"
                        ? "Playoff finish"
                        : key}
                    <Input
                      aria-label={`${t.name} ${key}`}
                      type="number"
                      step={key === "points" ? "0.01" : "1"}
                      min={key === "finish" ? 1 : 0}
                      max={key === "finish" ? state.teams.length : undefined}
                      name={`${key}-${t.id}`}
                      required={key !== "finish"}
                    />
                  </label>
                ))}
              </fieldset>
            ))}
          </div>
          <Button className="mt-4" disabled={busy}>
            Close reviewed season
          </Button>
        </form>
      )}
      {state.status === "closed" && (
        <Button
          disabled={busy}
          onClick={() => run(() => dynastyApi.rollover(state.league_id))}
        >
          Open {state.current_season + 1} freshman offseason
        </Button>
      )}
      {state.current_season > state.startup_season && (
        <label className={field}>
          Season archive
          <select
            className="rounded border bg-background p-2"
            value={history ?? ""}
            onChange={(e) => setHistory(Number(e.target.value))}
          >
            <option value="" disabled>
              Select closed season
            </option>
            {Array.from(
              { length: state.current_season - state.startup_season },
              (_, i) => state.startup_season + i,
            ).map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
        </label>
      )}
      {historical.isFetching && <p role="status">Loading archive…</p>}
      {historical.error && <p role="alert">{errorMessage(historical.error)}</p>}
      {historical.data && (
        <p>
          {historical.data.season}: {historical.data.rosters.length} rostered
          players preserved.{" "}
          {historical.data.results
            .map(
              (r) =>
                `${state.teams.find((t) => t.id === r.team_id)?.name}: ${r.wins}-${r.losses}-${r.ties}`,
            )
            .join("; ")}
        </p>
      )}
    </section>
  );
}
