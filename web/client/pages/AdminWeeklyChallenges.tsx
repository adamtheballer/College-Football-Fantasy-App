import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import {
  type Challenge,
  type Config,
  type Game,
  type PoolPlayer,
  type Round,
  type Underdog,
  challengeError,
  deadlineText,
  useCurrentChallenges,
} from "@/hooks/use-weekly-challenges";

type Catalog = {
  season: number;
  week: number;
  games: Game[];
  players: PoolPlayer[];
};
function ConfigEditor({
  challenge: initial,
  catalog,
}: {
  challenge: Challenge;
  catalog: Catalog;
}) {
  const [c, setC] = useState(initial);
  const [config, setConfig] = useState<Config>(
    initial.draft_config ?? {
      game_ids: [],
      player_ids: [],
      featured_game_id: null,
      underdogs: [],
    },
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [reason, setReason] = useState("");
  const [audit, setAudit] = useState<unknown[] | null>(null);
  const editable = !c.published_at && c.state !== "Canceled";
  const toggleGame = (id: number) =>
    setConfig((old) => ({
      ...old,
      game_ids: old.game_ids.includes(id)
        ? old.game_ids.filter((g) => g !== id)
        : [...old.game_ids, id],
      underdogs: old.underdogs.filter((d) => d.game_id !== id),
      player_ids: old.player_ids.filter(
        (p) => catalog.players.find((x) => x.id === p)?.game_id !== id,
      ),
    }));
  const dog = (game: Game, changes: Partial<Underdog>) =>
    setConfig((old) => ({
      ...old,
      underdogs: [
        ...old.underdogs.filter((d) => d.game_id !== game.id),
        {
          game_id: game.id,
          team: "",
          points: 1,
          ...old.underdogs.find((d) => d.game_id === game.id),
          ...changes,
        },
      ],
    }));
  const act = async (action: string) => {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const base = `/admin/weekly-challenges/challenges/${c.id}`;
      if (action === "save") {
        const next = await apiPut<Challenge>(base, {
          ...config,
          expected_version: c.version,
        });
        setC(next);
        setConfig(next.draft_config!);
        setNotice("Draft configuration saved. Validate before publishing.");
      } else if (action === "validate") {
        const v = await apiPost<{
          valid: boolean;
          blockers: string[];
          lock_at: string | null;
        }>(`${base}/validate`, {});
        setNotice(
          v.valid
            ? `Configuration valid. Shared deadline: ${deadlineText(v.lock_at)}`
            : v.blockers.join(" "),
        );
      } else if (action === "audit")
        setAudit(await apiGet<unknown[]>(`${base}/audit`));
      else {
        const next = await apiPost<Challenge>(`${base}/${action}`, {
          expected_version: c.version,
          reason,
        });
        setC(next);
        setNotice(`${action} completed. ${next.state}`);
      }
    } catch (e) {
      setError(challengeError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <SurfaceCard className="space-y-4">
      <div className="flex flex-wrap justify-between gap-2">
        <h2 className="cfb-section-title text-xl">{c.name}</h2>
        <span className="text-sm">
          {c.state} · v{c.version}
        </span>
      </div>
      <p className="text-sm text-muted-foreground">{c.rules}</p>
      {editable ? (
        <>
          <p className="text-sm font-bold">
            Published slate ({config.game_ids.length} games)
          </p>
          <div className="max-h-80 space-y-3 overflow-auto rounded border border-border p-3">
            {catalog.games.map((g) => (
              <div key={g.id} className="space-y-2 border-b border-border pb-2">
                <label className="flex min-h-11 items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={config.game_ids.includes(g.id)}
                    onChange={() => toggleGame(g.id)}
                  />
                  <span>
                    {g.away_team} at {g.home_team}
                    <span className="block text-xs text-muted-foreground">
                      {deadlineText(g.start_date)} ·{" "}
                      {g.status ?? "Unknown status"}
                    </span>
                  </span>
                </label>
                {c.kind === "upset" && config.game_ids.includes(g.id) && (
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="text-xs">
                      Designated underdog
                      <select
                        className="cfb-control mt-1 block min-h-11 w-full p-2 text-base"
                        value={
                          config.underdogs.find((d) => d.game_id === g.id)
                            ?.team ?? ""
                        }
                        onChange={(e) => dog(g, { team: e.target.value })}
                      >
                        <option value="" disabled>
                          Administrator must choose
                        </option>
                        <option>{g.away_team}</option>
                        <option>{g.home_team}</option>
                      </select>
                    </label>
                    <label className="text-xs">
                      Fixed difficulty points
                      <input
                        className="cfb-control mt-1 block min-h-11 w-full p-2 text-base"
                        type="number"
                        min="1"
                        max="5"
                        step="1"
                        value={
                          config.underdogs.find((d) => d.game_id === g.id)
                            ?.points ?? 1
                        }
                        onChange={(e) =>
                          dog(g, { points: Number(e.target.value) })
                        }
                      />
                    </label>
                  </div>
                )}
              </div>
            ))}
          </div>
          {c.kind === "slate12" && (
            <label className="block text-sm">
              Featured total-score tiebreaker game
              <select
                className="cfb-control mt-1 block min-h-11 w-full p-2 text-base"
                value={config.featured_game_id ?? ""}
                onChange={(e) =>
                  setConfig((old) => ({
                    ...old,
                    featured_game_id: Number(e.target.value),
                  }))
                }
              >
                <option value="">Select featured game</option>
                {catalog.games
                  .filter((g) => config.game_ids.includes(g.id))
                  .map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.away_team} at {g.home_team}
                    </option>
                  ))}
              </select>
            </label>
          )}
          {c.kind === "fantasy5" && (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="text-sm font-bold">
                  Eligible pool ({config.player_ids.length})
                </h3>
                <Button
                  variant="outline"
                  onClick={() =>
                    setConfig((old) => ({
                      ...old,
                      player_ids: catalog.players
                        .filter((p) => old.game_ids.includes(p.game_id))
                        .map((p) => p.id),
                    }))
                  }
                >
                  Use all eligible players in slate
                </Button>
              </div>
              <div className="max-h-64 space-y-1 overflow-auto rounded border border-border p-3">
                {catalog.players
                  .filter((p) => config.game_ids.includes(p.game_id))
                  .map((p) => (
                    <label
                      key={p.id}
                      className="flex min-h-11 items-center gap-3 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={config.player_ids.includes(p.id)}
                        onChange={() =>
                          setConfig((old) => ({
                            ...old,
                            player_ids: old.player_ids.includes(p.id)
                              ? old.player_ids.filter((x) => x !== p.id)
                              : [...old.player_ids, p.id],
                          }))
                        }
                      />
                      {p.name} · {p.position} · {p.school}
                    </label>
                  ))}
              </div>
            </>
          )}
        </>
      ) : (
        <p className="text-sm">
          Published configuration is frozen. Deadline {deadlineText(c.lock_at)}.
          Changes require cancellation, not a silent slate replacement.
        </p>
      )}
      <label className="block text-sm">
        Audit reason
        <input
          className="cfb-control mt-1 block min-h-11 w-full p-2 text-base"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
          placeholder="Reason for publication, scoring, correction or cancellation"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        {editable && (
          <>
            <Button disabled={busy} onClick={() => void act("save")}>
              Save Configuration
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void act("validate")}
            >
              Validate Saved Draft
            </Button>
            <Button
              variant="outline"
              disabled={busy || !reason.trim()}
              onClick={() => void act("publish")}
            >
              Publish Saved Draft
            </Button>
          </>
        )}
        {c.published_at && (
          <>
            <Button
              disabled={busy || !reason.trim()}
              onClick={() => void act("score")}
            >
              Settle From Server Data
            </Button>
            <Button
              variant="outline"
              disabled={busy || !reason.trim()}
              onClick={() => void act("correct")}
            >
              Recalculate Correction
            </Button>
          </>
        )}
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => void act("audit")}
        >
          View Audit
        </Button>
        {c.state !== "Canceled" && (
          <Button
            variant="destructive"
            disabled={busy || !reason.trim()}
            onClick={() => {
              if (
                window.confirm(
                  "Cancel this challenge and withdraw its awards? History and the audit ledger are retained.",
                )
              )
                void act("cancel");
            }}
          >
            Cancel Challenge
          </Button>
        )}
      </div>
      {busy && <p role="status">Saving server changes…</p>}
      {notice && (
        <p role="status" className="text-sm">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-300">
          {error}
        </p>
      )}
      {audit && (
        <details open>
          <summary>Audit history</summary>
          <pre className="max-h-80 overflow-auto rounded border border-border p-3 text-xs">
            {JSON.stringify(audit, null, 2)}
          </pre>
        </details>
      )}
    </SurfaceCard>
  );
}

export default function AdminWeeklyChallenges() {
  const { user } = useAuth();
  const current = useCurrentChallenges(!!user?.isAdmin);
  const [season, setSeason] = useState(2026);
  const [week, setWeek] = useState(1);
  const [round, setRound] = useState<Round | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const initialized = useRef(false);
  useEffect(() => {
    if (current.data && !initialized.current) {
      setSeason(current.data.season);
      setWeek(current.data.week);
      initialized.current = true;
    }
  }, [current.data]);
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await apiPost<Round>(
        `/admin/weekly-challenges/rounds/${season}/${week}`,
        {},
      );
      const pool = await apiGet<Catalog>("/admin/weekly-challenges/catalog", {
        season,
        week,
      });
      setRound(r);
      setCatalog(pool);
    } catch (e) {
      setError(challengeError(e));
    } finally {
      setBusy(false);
    }
  };
  if (!user?.isAdmin) return <p role="alert">Administrator access required.</p>;
  return (
    <div className="mx-auto max-w-5xl space-y-5 pb-24 pt-3">
      <PageHeader
        title="Manage Weekly Challenges"
        description="Prepare canonical weekly slates, validate, then publish. Rules and weights freeze at publication."
      />
      <Button asChild variant="outline">
        <Link to="/weekly-challenges">Challenge Hub</Link>
      </Button>
      <SurfaceCard>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void load();
          }}
        >
          <label className="text-sm">
            Season
            <input
              className="cfb-control mt-1 block min-h-11 w-32 p-2 text-base"
              type="number"
              min="2000"
              max="2100"
              value={season}
              onChange={(e) => setSeason(Number(e.target.value))}
            />
          </label>
          <label className="text-sm">
            Week
            <input
              className="cfb-control mt-1 block min-h-11 w-24 p-2 text-base"
              type="number"
              min="1"
              max="15"
              value={week}
              onChange={(e) => setWeek(Number(e.target.value))}
            />
          </label>
          <Button type="submit" disabled={busy}>
            {busy ? "Loading…" : "Load / Prepare Week"}
          </Button>
        </form>
        {error && (
          <p role="alert" className="mt-3 text-red-300">
            {error}
          </p>
        )}
      </SurfaceCard>
      {round && catalog && (
        <>
          <p className="text-sm text-muted-foreground">
            {round.season} Week {round.week} · {catalog.games.length} canonical
            games · {catalog.players.length} eligible players. No slate or
            difficulty is guessed when source data is missing.
          </p>
          {round.challenges.filter(c => !["fanwars","millionaire","creator","survivor"].includes(c.kind)).map((c) => (
            <ConfigEditor
              key={`${round.id}:${c.id}`}
              challenge={c}
              catalog={catalog}
            />
          ))}
        </>
      )}
    </div>
  );
}
