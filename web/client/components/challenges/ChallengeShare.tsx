import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SurfaceCard } from "@/components/fantasy";
import { useAuth } from "@/hooks/use-auth";
import { apiChallengeWrite } from "@/lib/api";
import type { Challenge } from "@/hooks/use-weekly-challenges";
import { useServerClock } from "./ExperienceEntry";
const escape = (value: string) =>
  value.replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&apos;",
      })[c]!,
  );
export function ChallengeShare({ challenge: c }: { challenge: Challenge }) {
  const x = c.experience!;
  const { user } = useAuth();
  const time = useServerClock(c.server_now);
  const locked = !!c.lock_at && time >= Date.parse(c.lock_at);
  const [showLineup, setShowLineup] = useState(false),
    [notice, setNotice] = useState("");
  const title =
    c.kind === "fanwars"
      ? x.allegiance && x.school_week_rank
        ? `I helped ${x.allegiance.name} climb to #${x.school_week_rank} in CFFB Fan Wars. Represent your school.`
        : "Represent your school in CFFB Fan Wars."
      : c.kind === "millionaire"
        ? "My $100 CFFB Fantasy Millionaire Lineup"
        : c.kind === "creator"
          ? x.comparison === "BEAT THE CREATOR"
            ? `I Beat ${x.creator?.name}!`
            : `Can You Beat ${x.creator?.name ?? "the Creator"}?`
          : x.survivor_status === "eliminated"
            ? `My CFFB Last Fan Standing streak ended at ${x.weeks_survived} weeks.`
            : x.weeks_survived > 0
              ? `Another week survived! ${x.weeks_survived} weeks in CFFB Last Fan Standing.`
              : "I'm joining CFFB Last Fan Standing.";
  const url = new URL(
    `/weekly-challenges/experiences/${c.id}`,
    "https://collegefantasyfootball.org",
  );
  if (x.creator) url.searchParams.set("ref", x.creator.slug);
  const lines = [
    `Week ${x.week} · ${x.season}`,
    title,
    ...(c.kind === "millionaire" && c.entry && (locked || showLineup)
      ? c.entry.selections.map((p) => {
          const player = c.players.find((v) => v.id === p.player_id);
          return `${p.slot}: ${player?.name ?? "Selected player"} · ${player?.school ?? ""} · $${x.salaries.find((v) => v.player_id === p.player_id)?.salary ?? "—"}`;
        })
      : []),
    ...(c.kind === "millionaire" && c.entry
      ? [
          `Virtual salary: $${c.entry.selections.reduce((sum, p) => sum + (x.salaries.find((v) => v.player_id === p.player_id)?.salary ?? 0), 0)}`,
        ]
      : []),
    ...(c.state.includes("Final") && x.your_points !== null
      ? [
          `${x.your_points} ${c.kind === "survivor" ? "weeks survived" : "points"} · Rank #${x.your_rank ?? "—"}`,
          ...(x.best_performer ? [`Best performer: ${x.best_performer}`] : []),
        ]
      : []),
    ...(c.kind === "creator" && x.comparison
      ? [
          `${x.comparison} · You ${x.your_points} vs. creator ${x.creator_score} points`,
        ]
      : []),
    ...(c.kind === "survivor" ? [`${x.weeks_survived} weeks survived`] : []),
    url.toString(),
  ];
  const tracked = () => {
    if (
      user &&
      navigator.doNotTrack !== "1" &&
      localStorage.getItem(`cffb_analytics_opt_out_${user.id}`) !== "true"
    )
      void apiChallengeWrite(user.id, "POST", "/weekly-challenges/events", {
        event_type: "share",
        challenge_id: c.id,
      }).catch(() => {});
  };
  const share = async () => {
    try {
      if (navigator.share)
        await navigator.share({
          title: "CFFB Weekly Challenges",
          text: lines.slice(0, -1).join("\n"),
          url: url.toString(),
        });
      else {
        await navigator.clipboard.writeText(lines.join("\n"));
        setNotice("Challenge link copied.");
      }
      tracked();
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError"))
        setNotice("Sharing unavailable. Copy the challenge link below.");
    }
  };
  const download = () => {
    const wrap = lines.flatMap(
      (line) => line.match(/.{1,48}(?:\s|$)|.{1,48}/g) ?? [line],
    );
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="${280 + wrap.length * 48}" viewBox="0 0 1080 ${280 + wrap.length * 48}"><rect width="100%" height="100%" fill="#111820"/><rect width="1080" height="12" fill="#48a9f1"/><text x="64" y="110" font-family="Arial,sans-serif" font-size="52" font-weight="bold" fill="#48a9f1">CFFB · WEEKLY CHALLENGES</text>${wrap.map((s, i) => `<text x="64" y="${210 + i * 48}" font-family="Arial,sans-serif" font-size="32" fill="#f5f5f5">${escape(s)}</text>`).join("")}</svg>`;
    const blob = new Blob([svg], { type: "image/svg+xml" }),
      href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = `cffb-${c.kind}-week-${x.week}.svg`;
    a.click();
    URL.revokeObjectURL(href);
    tracked();
  };
  return (
    <SurfaceCard className="space-y-3">
      <h2 className="cfb-section-title text-xl">Share Your Challenge</h2>
      <p className="text-sm font-bold">{title}</p>
      {c.kind === "millionaire" && !locked && (
        <label className="flex min-h-11 items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={showLineup}
            onChange={(e) => setShowLineup(e.target.checked)}
          />
          Include my player choices before lock (hidden by default)
        </label>
      )}
      <div className="flex flex-wrap gap-3">
        <Button onClick={() => void share()}>Share</Button>
        <Button variant="outline" onClick={download}>
          {c.state.includes("Final")
            ? "Download Result Card"
            : "Download Share Card"}
        </Button>
      </div>
      <a
        className="block break-all text-xs text-primary underline"
        href={url.toString()}
      >
        {url.toString()}
      </a>
      {notice && (
        <p role="status" className="text-sm">
          {notice}
        </p>
      )}
    </SurfaceCard>
  );
}
