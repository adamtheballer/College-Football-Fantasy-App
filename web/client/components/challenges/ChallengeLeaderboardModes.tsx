import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { SurfaceCard } from "@/components/fantasy";
import { ExperienceLeaderboard } from "./ExperienceLeaderboard";
import { ChallengeResults } from "@/pages/WeeklyChallengeDetail";
import {
  CHALLENGE_NAMES,
  useChallenge,
  type Round,
} from "@/hooks/use-weekly-challenges";
import {
  EXPERIENCE_KINDS,
  isExperience,
} from "@/hooks/use-challenge-experiences";
export function ChallengeLeaderboardFilters() {
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") ?? "overall";
  return (
    <div className="flex flex-wrap gap-2" aria-label="Leaderboard mode">
      {[
        ["overall", "Overall"],
        ...EXPERIENCE_KINDS.map((k) => [k, CHALLENGE_NAMES[k]]),
        ["existing", "Existing Challenges"],
      ].map(([key, label]) => (
        <Button
          key={key}
          variant={mode === key ? "default" : "outline"}
          aria-pressed={mode === key}
          onClick={() => {
            const p = new URLSearchParams(params);
            p.set("mode", key);
            p.delete("competition");
            setParams(p);
          }}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
export function ChallengeModeStandings({
  round,
}: {
  round: Round | undefined;
}) {
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") ?? "overall";
  const candidates =
    round?.challenges.filter((c) =>
      mode === "existing" ? !isExperience(c.kind) : c.kind === mode,
    ) ?? [];
  const id = Number(params.get("competition"));
  const selected = candidates.find((c) => c.id === id) ?? candidates[0];
  const detail = useChallenge(selected?.id ?? 0);
  return (
    <>
      <label className="block text-xs">
        Competition
        <select
          aria-label="Leaderboard competition"
          className="cfb-control mt-2 min-h-11 w-full p-3 text-base"
          value={selected?.id ?? ""}
          onChange={(e) => {
            const p = new URLSearchParams(params);
            p.set("competition", e.target.value);
            setParams(p);
          }}
        >
          {candidates.length === 0 && (
            <option value="">No published competition</option>
          )}
          {candidates.map((c) => (
            <option value={c.id} key={c.id}>
              {c.experience?.creator
                ? `Beat ${c.experience.creator.name}`
                : c.name}
            </option>
          ))}
        </select>
      </label>
      {!selected && (
        <SurfaceCard>
          <p className="text-sm">
            No published competition for this mode in the selected week.
          </p>
        </SurfaceCard>
      )}
      {selected && detail.isPending && (
        <p role="status">Loading competition standings…</p>
      )}
      {selected && detail.isError && (
        <p role="alert">
          Competition standings unavailable.{" "}
          <button className="underline" onClick={() => void detail.refetch()}>
            Retry
          </button>
        </p>
      )}
      {detail.data &&
        selected &&
        (isExperience(detail.data.kind) ? (
          <ExperienceLeaderboard challenge={detail.data} />
        ) : (
          <ChallengeResults challenge={detail.data} />
        ))}
    </>
  );
}
