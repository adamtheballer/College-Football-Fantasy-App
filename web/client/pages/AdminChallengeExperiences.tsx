import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { apiGet, apiChallengeWrite } from "@/lib/api";
import {
  type Challenge,
  type Game,
  type PoolPlayer,
  CHALLENGE_NAMES,
  challengeError,
  useCurrentChallenges,
} from "@/hooks/use-weekly-challenges";
import {
  EXPERIENCE_KINDS,
  type ExperienceKind,
  type ExperienceConfig,
  type Creator,
  type Series,
} from "@/hooks/use-challenge-experiences";
const empty: ExperienceConfig = {
  expected_version: 0,
  game_ids: [],
  player_ids: [],
  salaries: [],
  creator_picks: [],
  correct_points: 10,
  minimum_fans: 3,
  rivalries: [],
};
type Catalog = {
  season: number;
  week: number;
  games: Game[];
  players: PoolPlayer[];
};

function Editor({ c, catalog }: { c: Challenge; catalog: Catalog }) {
  const { user } = useAuth();
  const cache = useQueryClient();
  const [config, setConfig] = useState<ExperienceConfig | null>(null),
    [reason, setReason] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [valid, setValid] = useState(false),
    [dirty, setDirty] = useState(false),
    [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["weekly-challenges", "admin-config", user?.id, c.id, c.version],
    enabled: !!user?.isAdmin,
    queryFn: () =>
      apiGet<ExperienceConfig>(
        `/admin/weekly-challenges/experiences/${c.id}/configuration`,
      ),
  });
  const draft = config ?? query.data ?? empty;
  const editable = !c.published_at && c.state !== "Canceled";
  const update = (next: ExperienceConfig) => {
    setConfig(next);
    setDirty(true);
    setValid(false);
    setNotice("");
  };
  const act = async (action: string) => {
    if (!user) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const base = `/admin/weekly-challenges/challenges/${c.id}`;
      if (action === "save") {
        await apiChallengeWrite(
          user.id,
          "PUT",
          `/admin/weekly-challenges/experiences/${c.id}`,
          { ...draft, expected_version: c.version },
        );
        setConfig(null);
        setDirty(false);
        setNotice("Configuration saved. Validate before publishing.");
      } else if (action === "validate") {
        const v = await apiChallengeWrite<{
          valid: boolean;
          blockers: string[];
        }>(user.id, "POST", `${base}/validate`, {});
        setValid(v.valid);
        setNotice(
          v.valid
            ? "Validation passed. Publication requires your review reason."
            : v.blockers.join(" "),
        );
      } else if (action === "suggest") {
        const rows = await apiGet<{ player_id: number; salary: number }[]>(
          `/admin/weekly-challenges/experiences/${c.id}/salary-suggestions`,
        );
        const map = new Map(draft.salaries.map((p) => [p.player_id, p]));
        for (const r of rows)
          if (draft.player_ids.includes(r.player_id))
            map.set(r.player_id, { player_id: r.player_id, salary: r.salary });
        update({ ...draft, salaries: [...map.values()] });
        setNotice(
          `Applied ${rows.filter((r) => draft.player_ids.includes(r.player_id)).length} suggestions for review. Missing projections stay unpriced.`,
        );
      } else if (action === "visibility") {
        await apiChallengeWrite(
          user.id,
          "PUT",
          `/admin/weekly-challenges/experiences/${c.id}/visibility`,
          {
            expected_version: c.version,
            enabled: !c.experience!.enabled,
            reason,
          },
        );
      } else {
        await apiChallengeWrite(user.id, "POST", `${base}/${action}`, {
          expected_version: c.version,
          reason,
        });
        setNotice(`${action} completed.`);
      }
      await cache.invalidateQueries({ queryKey: ["weekly-challenges"] });
    } catch (e) {
      setError(challengeError(e));
    } finally {
      setBusy(false);
    }
  };
  const [decisionGame, setDecisionGame] = useState("");
  const decision = async (revoke = false) => {
    if (!user) return;
    setBusy(true);
    setError("");
    try {
      await apiChallengeWrite(
        user.id,
        "POST",
        `/admin/weekly-challenges/experiences/${c.id}/${revoke ? "revoke-void-advance" : "void-advance"}`,
        { expected_version: c.version, game_id: Number(decisionGame), reason },
      );
      await cache.invalidateQueries({ queryKey: ["weekly-challenges"] });
      setNotice("Published void-and-advance decision recorded.");
    } catch (e) {
      setError(challengeError(e));
    } finally {
      setBusy(false);
    }
  };
  const correctCreator = async () => {
    if (!user) return;
    setBusy(true);
    setError("");
    try {
      await apiChallengeWrite(
        user.id,
        "PUT",
        `/admin/weekly-challenges/experiences/${c.id}/creator-correction`,
        { expected_version: c.version, picks: draft.creator_picks, reason },
      );
      await cache.invalidateQueries({ queryKey: ["weekly-challenges"] });
      setNotice("Creator correction audited and scores recalculated.");
    } catch (e) {
      setError(challengeError(e));
    } finally {
      setBusy(false);
    }
  };
  const analytics = useQuery({
    queryKey: ["weekly-challenges", "analytics", user?.id, c.id],
    enabled: !!user?.isAdmin,
    queryFn: () =>
      apiGet<Record<string, number>>(
        `/admin/weekly-challenges/experiences/${c.id}/analytics`,
      ),
  });
  const audit = useQuery({
    queryKey: ["weekly-challenges", "audit", user?.id, c.id, c.version],
    enabled: !!user?.isAdmin,
    queryFn: () =>
      apiGet<{ id: number; action: string; at: string; details: unknown }[]>(
        `/admin/weekly-challenges/challenges/${c.id}/audit`,
      ),
  });
  const toggle = (id: number) =>
    update({
      ...draft,
      game_ids: draft.game_ids.includes(id)
        ? draft.game_ids.filter((v) => v !== id)
        : [...draft.game_ids, id],
      player_ids: draft.player_ids.filter(
        (pid) => catalog.players.find((p) => p.id === pid)?.game_id !== id,
      ),
      salaries: draft.salaries.filter(
        (s) =>
          catalog.players.find((p) => p.id === s.player_id)?.game_id !== id,
      ),
      creator_picks: draft.creator_picks.filter((p) => p.game_id !== id),
    });
  return (
    <SurfaceCard className="space-y-4">
      <div className="flex flex-wrap justify-between gap-2">
        <h2 className="cfb-section-title text-xl">
          {c.experience?.creator ? `Beat ${c.experience.creator.name}` : c.name}
        </h2>
        <span className="text-xs">
          {c.state} · v{c.version} ·{" "}
          {c.experience?.enabled ? "Visible" : "Hidden"}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        Week {c.experience?.week} ·{" "}
        {c.experience?.series?.name ?? c.rules_version}
      </p>
      {query.isPending && <p role="status">Loading saved configuration…</p>}
      {query.isError && (
        <p role="alert">
          Configuration could not be loaded.{" "}
          <button onClick={() => void query.refetch()} className="underline">
            Retry
          </button>
        </p>
      )}
      {editable && query.data && (
        <>
          <h3 className="cfb-micro-label">
            Published Slate · {draft.game_ids.length} games
          </h3>
          <div className="max-h-64 space-y-2 overflow-auto rounded border border-border p-3">
            {catalog.games.map((g) => (
              <label
                key={g.id}
                className="flex min-h-11 items-center gap-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={draft.game_ids.includes(g.id)}
                  onChange={() => toggle(g.id)}
                />
                <span>
                  {g.away_team} at {g.home_team}
                  <span className="block text-xs text-muted-foreground">
                    {g.start_date
                      ? new Date(g.start_date).toLocaleString()
                      : "Kickoff unverified"}{" "}
                    · {g.status}
                  </span>
                </span>
              </label>
            ))}
          </div>
          {c.kind === "millionaire" && (
            <>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => void act("suggest")}
                >
                  Suggest Salaries for Review
                </Button>
                <input
                  aria-label="Filter salary pool"
                  placeholder="Filter salary pool"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="cfb-control min-h-11 p-2 text-base"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Suggested salary v1 = round(0.8 × published fantasy projection),
                capped to $1–$30. Every included player needs a reviewed salary;
                missing projections receive no price.
              </p>
              <div className="max-h-80 space-y-2 overflow-auto rounded border border-border p-3">
                {catalog.players
                  .filter(
                    (p) =>
                      draft.game_ids.includes(p.game_id) &&
                      `${p.name} ${p.school}`
                        .toLowerCase()
                        .includes(search.toLowerCase()),
                  )
                  .map((p) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between gap-3 border-b border-border py-2"
                    >
                      <label className="flex min-h-11 items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={draft.player_ids.includes(p.id)}
                          onChange={() =>
                            update({
                              ...draft,
                              player_ids: draft.player_ids.includes(p.id)
                                ? draft.player_ids.filter((id) => id !== p.id)
                                : [...draft.player_ids, p.id],
                              salaries: draft.salaries.filter(
                                (s) => s.player_id !== p.id,
                              ),
                            })
                          }
                        />
                        <span>
                          {p.name}
                          <span className="block text-xs text-muted-foreground">
                            {p.position} · {p.school}
                          </span>
                        </span>
                      </label>
                      {draft.player_ids.includes(p.id) && (
                        <input
                          aria-label={`Salary for ${p.name}`}
                          type="number"
                          min="1"
                          max="100"
                          step="0.01"
                          value={
                            draft.salaries.find((s) => s.player_id === p.id)
                              ?.salary ?? ""
                          }
                          onChange={(e) =>
                            update({
                              ...draft,
                              salaries: [
                                ...draft.salaries.filter(
                                  (s) => s.player_id !== p.id,
                                ),
                                ...(e.target.value
                                  ? [
                                      {
                                        player_id: p.id,
                                        salary: Number(e.target.value),
                                      },
                                    ]
                                  : []),
                              ],
                            })
                          }
                          className="cfb-control min-h-11 w-20 p-2 text-base"
                        />
                      )}
                    </div>
                  ))}
              </div>
            </>
          )}
          {c.kind === "fanwars" && (
            <>
              <label className="block text-sm">
                Minimum active fans
                <input
                  type="number"
                  min="2"
                  max="1000"
                  className="cfb-control ml-3 min-h-11 w-24 p-2 text-base"
                  value={draft.minimum_fans}
                  onChange={(e) =>
                    update({ ...draft, minimum_fans: Number(e.target.value) })
                  }
                />
              </label>
              <details>
                <summary className="min-h-11 cursor-pointer text-sm font-bold">
                  Featured fan rivalries
                </summary>
                {draft.rivalries.map(([a, b], i) => (
                  <div key={i} className="mb-2 grid grid-cols-2 gap-2">
                    {[a, b].map((id, j) => (
                      <select
                        key={j}
                        aria-label={`Rivalry ${i + 1} school ${j + 1}`}
                        value={id}
                        onChange={(e) =>
                          update({
                            ...draft,
                            rivalries: draft.rivalries.map((r, index) =>
                              index === i
                                ? j === 0
                                  ? [Number(e.target.value), r[1]]
                                  : [r[0], Number(e.target.value)]
                                : r,
                            ),
                          })
                        }
                        className="cfb-control min-h-11 p-2 text-base"
                      >
                        {c.experience?.schools.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    ))}
                  </div>
                ))}
                <Button
                  variant="outline"
                  onClick={() => {
                    const values = c.experience?.schools ?? [];
                    if (values.length > 1)
                      update({
                        ...draft,
                        rivalries: [
                          ...draft.rivalries,
                          [values[0].id, values[1].id],
                        ],
                      });
                  }}
                >
                  Add Rivalry
                </Button>
              </details>
            </>
          )}
          {(c.kind === "fanwars" || c.kind === "creator") && (
            <label className="block text-sm">
              Points per correct prediction
              <input
                type="number"
                min="1"
                max="100"
                className="cfb-control ml-3 min-h-11 w-24 p-2 text-base"
                value={draft.correct_points}
                onChange={(e) =>
                  update({ ...draft, correct_points: Number(e.target.value) })
                }
              />
            </label>
          )}
        </>
      )}
      {c.kind === "creator" && query.data && (
        <>
          <h3 className="cfb-micro-label">Approved Creator Picks</h3>
          <p className="text-xs text-muted-foreground">
            Exactly 10 picks are required before publication. After publication,
            only a disclosed administrative correction can change them.
          </p>
          <div className="max-h-72 space-y-2 overflow-auto">
            {(editable
              ? catalog.games.filter((g) => draft.game_ids.includes(g.id))
              : c.games
            ).map((g) => (
              <label key={g.id} className="block text-xs">
                {g.away_team} at {g.home_team}
                <select
                  aria-label={`Creator pick ${g.id}`}
                  value={
                    draft.creator_picks.find((p) => p.game_id === g.id)?.team ??
                    ""
                  }
                  onChange={(e) =>
                    update({
                      ...draft,
                      creator_picks: [
                        ...draft.creator_picks.filter(
                          (p) => p.game_id !== g.id,
                        ),
                        ...(e.target.value
                          ? [{ game_id: g.id, team: e.target.value }]
                          : []),
                      ],
                    })
                  }
                  className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
                >
                  <option value="">Select approved pick</option>
                  <option>{g.away_team}</option>
                  <option>{g.home_team}</option>
                </select>
              </label>
            ))}
          </div>
          {!editable && (
            <Button
              variant="outline"
              disabled={busy || reason.trim().length < 10}
              onClick={() => void correctCreator()}
            >
              Apply Audited Creator Correction
            </Button>
          )}
        </>
      )}
      <label className="block text-sm">
        Review / correction reason
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="cfb-control mt-2 min-h-20 w-full p-3 text-base"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        {editable && (
          <>
            <Button
              disabled={busy || !query.data}
              onClick={() => void act("save")}
            >
              Save Configuration
            </Button>
            <Button
              variant="outline"
              disabled={busy || dirty}
              onClick={() => void act("validate")}
            >
              Validate Saved Configuration
            </Button>
            <Button
              disabled={busy || dirty || !valid || reason.trim().length < 10}
              onClick={() => void act("publish")}
            >
              Publish Competition
            </Button>
          </>
        )}
        {!editable && c.state !== "Canceled" && (
          <>
            <Button
              variant="outline"
              disabled={busy || reason.trim().length < 10}
              onClick={() => void act("score")}
            >
              Recalculate Verified Results
            </Button>
            <Button
              variant="outline"
              disabled={busy || reason.trim().length < 10}
              onClick={() => void act("cancel")}
            >
              Cancel Competition
            </Button>
          </>
        )}
        <Button
          variant="outline"
          disabled={busy || reason.trim().length < 5}
          onClick={() => void act("visibility")}
        >
          {c.experience?.enabled ? "Hide Competition" : "Show Competition"}
        </Button>
      </div>
      {c.kind === "survivor" && c.published_at && (
        <div className="space-y-3 border-t border-border pt-3">
          <label className="block text-sm">
            Official tie / void game decision
            <select
              value={decisionGame}
              onChange={(e) => setDecisionGame(e.target.value)}
              className="cfb-control mt-2 min-h-11 w-full p-2 text-base"
            >
              <option value="">Choose game</option>
              {c.games.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.away_team} at {g.home_team} · {g.status}
                </option>
              ))}
            </select>
          </label>
          <Button
            variant="outline"
            disabled={busy || !decisionGame || reason.trim().length < 10}
            onClick={() => void decision(false)}
          >
            Confirm Published Void-and-Advance Policy
          </Button>
          <Button
            className="ml-2"
            variant="outline"
            disabled={busy || !decisionGame || reason.trim().length < 10}
            onClick={() => void decision(true)}
          >
            Revoke Prior Void Decision
          </Button>
        </div>
      )}
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
      <details>
        <summary className="min-h-11 cursor-pointer text-sm font-bold">
          Participation Analytics
        </summary>
        {analytics.isError ? (
          <p role="alert">Analytics unavailable.</p>
        ) : (
          <dl className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(analytics.data ?? {})
              .filter(([key]) => key !== "challenge_id")
              .map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd className="font-bold">{value}</dd>
                </div>
              ))}
          </dl>
        )}
      </details>
      <details>
        <summary className="min-h-11 cursor-pointer text-sm font-bold">
          Audit History
        </summary>
        {audit.isError ? (
          <p role="alert">Audit history unavailable.</p>
        ) : (
          audit.data?.map((a) => (
            <div key={a.id} className="border-t border-border py-2 text-xs">
              <strong>{a.action}</strong> · {new Date(a.at).toLocaleString()}
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap">
                {JSON.stringify(a.details, null, 2)}
              </pre>
            </div>
          ))
        )}
      </details>
    </SurfaceCard>
  );
}

export default function AdminChallengeExperiences() {
  const { user } = useAuth();
  const current = useCurrentChallenges();
  const cache = useQueryClient();
  const [season, setSeason] = useState(new Date().getFullYear()),
    [week, setWeek] = useState(8),
    [kind, setKind] = useState<ExperienceKind>("fanwars"),
    [creatorId, setCreatorId] = useState(""),
    [seriesId, setSeriesId] = useState(""),
    [opens, setOpens] = useState(""),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const enabled = !!user?.isAdmin;
  const creators = useQuery({
    queryKey: ["weekly-challenges", "admin-creators", user?.id],
    enabled,
    queryFn: () => apiGet<Creator[]>("/admin/weekly-challenges/creators"),
  });
  const series = useQuery({
    queryKey: ["weekly-challenges", "admin-series", user?.id],
    enabled,
    queryFn: () => apiGet<Series[]>("/admin/weekly-challenges/survivor-series"),
  });
  const list = useQuery({
    queryKey: [
      "weekly-challenges",
      "admin-experiences",
      user?.id,
      season,
      week,
    ],
    enabled,
    queryFn: () =>
      apiGet<Challenge[]>("/admin/weekly-challenges/experiences", {
        season,
        week,
      }),
  });
  const catalog = useQuery({
    queryKey: ["weekly-challenges", "admin-catalog", user?.id, season, week],
    enabled,
    queryFn: () =>
      apiGet<Catalog>("/admin/weekly-challenges/catalog", { season, week }),
  });
  const [editingCreator, setEditingCreator] = useState<number | null>(null);
  const [name, setName] = useState(""),
    [slug, setSlug] = useState(""),
    [description, setDescription] = useState(""),
    [logo, setLogo] = useState(""),
    [youtube, setYoutube] = useState(""),
    [authorized, setAuthorized] = useState(false),
    [creatorActive, setCreatorActive] = useState(false);
  const [seriesName, setSeriesName] = useState(""),
    [startWeek, setStartWeek] = useState(8),
    [endWeek, setEndWeek] = useState(13),
    [firstLock, setFirstLock] = useState("");
  const run = async (path: string, payload: unknown) => {
    if (!user) return;
    setBusy(true);
    setError("");
    try {
      await apiChallengeWrite(
        user.id,
        path.startsWith("creators/") ? "PUT" : "POST",
        `/admin/weekly-challenges/${path}`,
        payload,
      );
      setNotice(
        "Saved. Configure, validate and publish the competition separately.",
      );
      await cache.invalidateQueries({ queryKey: ["weekly-challenges"] });
    } catch (e) {
      setError(challengeError(e));
    } finally {
      setBusy(false);
    }
  };
  if (!user?.isAdmin)
    return (
      <SurfaceCard>
        <p role="alert">Administrator access required.</p>
      </SurfaceCard>
    );
  return (
    <div className="mx-auto max-w-6xl space-y-5 pb-24 pt-3">
      <PageHeader
        title="Challenge Management"
        description="Publish reviewed real slates. Draft competitions remain unavailable for entry."
      />
      <div className="flex flex-wrap gap-3">
        <Button asChild variant="outline">
          <Link to="/weekly-challenges">Challenge Hub</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/admin/weekly-challenges">
            Manage Existing Five Formats
          </Link>
        </Button>
        <Button
          variant="outline"
          onClick={() => {
            if (current.data) {
              setSeason(current.data.season);
              setWeek(current.data.week);
            }
          }}
        >
          Current Week
        </Button>
      </div>
      <SurfaceCard className="space-y-4">
        <h2 className="cfb-section-title text-xl">Prepare Competition</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-xs">
            Season
            <input
              type="number"
              min="2000"
              max="2100"
              className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
              value={season}
              onChange={(e) => setSeason(Number(e.target.value))}
            />
          </label>
          <label className="text-xs">
            Week
            <input
              type="number"
              min="1"
              max="15"
              className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
              value={week}
              onChange={(e) => setWeek(Number(e.target.value))}
            />
          </label>
          <label className="text-xs">
            Mode
            <select
              className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
              value={kind}
              onChange={(e) => setKind(e.target.value as ExperienceKind)}
            >
              {EXPERIENCE_KINDS.map((k) => (
                <option key={k} value={k}>
                  {CHALLENGE_NAMES[k]}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs">
            Entry opening (local time)
            <input
              type="datetime-local"
              value={opens}
              onChange={(e) => setOpens(e.target.value)}
              className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
            />
          </label>
          {kind === "creator" && (
            <label className="text-xs">
              Creator
              <select
                className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
                value={creatorId}
                onChange={(e) => setCreatorId(e.target.value)}
              >
                <option value="">Choose registered creator</option>
                {creators.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} · {c.authorized ? "Approved" : "Unapproved"}
                  </option>
                ))}
              </select>
            </label>
          )}
          {kind === "survivor" && (
            <label className="text-xs">
              Series
              <select
                className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
                value={seriesId}
                onChange={(e) => setSeriesId(e.target.value)}
              >
                <option value="">Choose series</option>
                {series.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {s.start_week}–{s.end_week}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <Button
          disabled={
            busy ||
            !opens ||
            (kind === "creator" && !creatorId) ||
            (kind === "survivor" && !seriesId)
          }
          onClick={() =>
            void run("experiences", {
              season,
              week,
              kind,
              entry_open_at: new Date(opens).toISOString(),
              creator_id: kind === "creator" ? Number(creatorId) : null,
              series_id: kind === "survivor" ? Number(seriesId) : null,
            })
          }
        >
          Create Draft Competition
        </Button>
      </SurfaceCard>
      <SurfaceCard>
        <details>
          <summary className="min-h-11 cursor-pointer font-bold">
            Register Approved Creator
          </summary>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[
              ["Name", name, setName],
              ["URL slug", slug, setSlug],
              ["Description", description, setDescription],
              ["Approved logo asset /assets/…", logo, setLogo],
              ["YouTube HTTPS link", youtube, setYoutube],
            ].map(([label, value, setter]) => (
              <label key={label as string} className="text-xs">
                {label as string}
                <input
                  className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
                  value={value as string}
                  onChange={(e) =>
                    (setter as (s: string) => void)(e.target.value)
                  }
                />
              </label>
            ))}
            <label className="flex min-h-11 items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={authorized}
                onChange={(e) => setAuthorized(e.target.checked)}
              />
              Participation and branding are authorized
            </label>
            <label className="flex min-h-11 items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={creatorActive}
                onChange={(e) => setCreatorActive(e.target.checked)}
              />
              Active directory profile
            </label>
          </div>
          <label className="mt-3 block text-xs">
            Upload approved PNG/JPEG logo (250 KB maximum)
            <input
              type="file"
              accept="image/png,image/jpeg"
              className="mt-2 block min-h-11 max-w-full text-sm"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                if (file.size > 250 * 1024) {
                  setError(
                    "Use an approved image of 250 KB or less, or reference the original bundled asset.",
                  );
                  return;
                }
                const reader = new FileReader();
                reader.onload = () => setLogo(String(reader.result));
                reader.readAsDataURL(file);
              }}
            />
          </label>
          {logo && (
            <img
              src={logo}
              alt="Approved creator logo preview"
              className="mt-3 h-16 w-16 object-contain"
            />
          )}
          <p className="my-3 text-xs text-muted-foreground">
            Sponsorship alone does not authorize a creator contest. Do not
            publish predictions until the creator has provided and approved
            them.
          </p>
          <Button
            disabled={busy || !name || !slug}
            onClick={() =>
              void run(
                editingCreator ? `creators/${editingCreator}` : "creators",
                {
                  name,
                  slug,
                  description,
                  logo_url: logo || null,
                  links: youtube ? { YouTube: youtube } : {},
                  authorized,
                  active: creatorActive,
                },
              )
            }
          >
            {editingCreator ? "Update Creator" : "Register Creator"}
          </Button>
          <Button
            variant="outline"
            className="ml-2"
            onClick={() => {
              setEditingCreator(null);
              setName("");
              setSlug("");
              setDescription("");
              setLogo("");
              setYoutube("");
              setAuthorized(false);
              setCreatorActive(false);
            }}
          >
            Clear Form
          </Button>
          <div className="mt-4 space-y-2">
            {creators.data?.map((c) => (
              <div
                key={c.id}
                className="flex flex-wrap items-center justify-between gap-3 border-t border-border py-3 text-sm"
              >
                <span>
                  {c.name} · {c.active ? "Active" : "Inactive"} ·{" "}
                  {c.authorized ? "Approved" : "Unapproved"}
                </span>
                <Button
                  variant="outline"
                  onClick={() => {
                    setEditingCreator(c.id);
                    setName(c.name);
                    setSlug(c.slug);
                    setDescription(c.description);
                    setLogo(c.logo_url ?? "");
                    setYoutube(c.links.YouTube ?? "");
                    setAuthorized(c.authorized);
                    setCreatorActive(c.active);
                  }}
                >
                  Edit Profile
                </Button>
              </div>
            ))}
          </div>
        </details>
      </SurfaceCard>
      <SurfaceCard>
        <details>
          <summary className="min-h-11 cursor-pointer font-bold">
            Start New Survivor Series
          </summary>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="text-xs">
              Series name
              <input
                value={seriesName}
                onChange={(e) => setSeriesName(e.target.value)}
                className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
              />
            </label>
            <label className="text-xs">
              Start week
              <input
                type="number"
                min="1"
                max="15"
                value={startWeek}
                onChange={(e) => setStartWeek(Number(e.target.value))}
                className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
              />
            </label>
            <label className="text-xs">
              End week
              <input
                type="number"
                min="1"
                max="15"
                value={endWeek}
                onChange={(e) => setEndWeek(Number(e.target.value))}
                className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
              />
            </label>
            <label className="text-xs">
              First lock (local time)
              <input
                type="datetime-local"
                value={firstLock}
                onChange={(e) => setFirstLock(e.target.value)}
                className="cfb-control mt-1 min-h-11 w-full p-2 text-base"
              />
            </label>
          </div>
          <p className="my-3 text-xs text-muted-foreground">
            Uses the Entry opening time above. Starting a new series preserves
            every previous series and its results.
          </p>
          <Button
            disabled={busy || !seriesName || !opens || !firstLock}
            onClick={() =>
              void run("survivor-series", {
                name: seriesName,
                season,
                start_week: startWeek,
                end_week: endWeek,
                entry_open_at: new Date(opens).toISOString(),
                first_lock_at: new Date(firstLock).toISOString(),
              })
            }
          >
            Create Survivor Series
          </Button>
        </details>
      </SurfaceCard>
      {notice && <p role="status">{notice}</p>}
      {error && (
        <p role="alert" className="text-red-300">
          {error}
        </p>
      )}
      {(creators.isError ||
        series.isError ||
        list.isError ||
        catalog.isError) && (
        <p role="alert">
          Some management data could not load.{" "}
          <button
            className="underline"
            onClick={() =>
              void cache.invalidateQueries({ queryKey: ["weekly-challenges"] })
            }
          >
            Retry
          </button>
        </p>
      )}
      {list.isPending && <p role="status">Loading configured competitions…</p>}
      {list.data?.length === 0 && (
        <SurfaceCard>
          <p className="text-sm">
            No expanded competitions configured for this week.
          </p>
        </SurfaceCard>
      )}
      {catalog.data &&
        list.data?.map((c) => (
          <Editor key={c.id} c={c} catalog={catalog.data} />
        ))}
    </div>
  );
}
