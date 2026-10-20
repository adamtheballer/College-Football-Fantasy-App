import { useEffect, useState } from "react";
import type { RankedPlayer } from "@/hooks/use-player-rankings";

export function PlayerRankingPortrait({
  player,
  large = false,
}: {
  player: Pick<RankedPlayer, "name" | "image_url">;
  large?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [player.image_url]);
  return (
    <div
      className={`${large ? "h-24 w-24" : "h-11 w-11"} shrink-0 overflow-hidden rounded-md border border-cfb-border-subtle bg-cfb-surface-elevated`}
    >
      {player.image_url && !failed ? (
        <img
          src={player.image_url}
          alt={player.name}
          className="h-full w-full object-contain object-bottom"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <span
          aria-label={`${player.name} portrait unavailable`}
          className="flex h-full items-center justify-center text-xl font-black text-cfb-text-muted"
        >
          {player.name
            .split(" ")
            .map((s) => s[0])
            .slice(0, 2)
            .join("")}
        </span>
      )}
    </div>
  );
}
