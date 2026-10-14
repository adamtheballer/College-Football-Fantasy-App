import { useEffect, useState } from "react";
import { UserRound, X } from "lucide-react";

import type { PlayerCardResponse } from "@/hooks/use-players";
import { PlayerAvailabilityIndicator, playerAvailabilityBadge, playerAvailabilityDotClass } from "@/lib/playerAvailability";
import { cn } from "@/lib/utils";

import type { PlayerCardModalPlayer } from "./PlayerCardModal";

type PlayerCardPalette = {
  headerBase: string;
  markerA: string;
  markerB: string;
  markerC: string;
  pill: string;
  silhouette: string;
};

export const formatPlayerCardPositionRank = (
  rank?: PlayerCardResponse["season_positional_rank"],
) => rank && Number.isInteger(rank.rank) && rank.rank > 0
  ? `${rank.position.toUpperCase()} ${rank.rank}`
  : "—";

export const formatPlayerCardStatus = (value?: string | null) => {
  const normalized = (value ?? "")
    .trim()
    .toUpperCase()
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ");

  // No reviewed injury report means the player is active until the injury
  // pipeline supplies a current designation. This keeps provider casing out
  // of the card so statuses never render as lowercase prose.
  if (["", "N A", "NA", "NONE", "UNREPORTED", "FULL", "HEALTHY", "AVAILABLE", "ACTIVE"].includes(normalized)) {
    return "ACTIVE";
  }
  return normalized;
};

export const resolvePlayerCardStatus = (
  card?: PlayerCardResponse | null,
  contextualStatus?: string | null,
) => formatPlayerCardStatus(card ? card.current_injury_status ?? "UNREPORTED" : contextualStatus ?? "UNREPORTED");

export function PlayerCardHeader({
  card,
  onClose,
  palette,
  player,
  position,
  title,
}: {
  card?: PlayerCardResponse | null;
  onClose: () => void;
  palette: PlayerCardPalette;
  player: PlayerCardModalPlayer;
  position: string;
  title: string;
}) {
  const headshotUrl = card?.about.headshot_url ?? card?.player.image_url ?? player.imageUrl;
  const [headshotFailed, setHeadshotFailed] = useState(false);
  useEffect(() => setHeadshotFailed(false), [headshotUrl]);
  const playerStatus = resolvePlayerCardStatus(card, player.status);
  const statusSource = playerStatus;
  const statusBadge = playerAvailabilityBadge(statusSource);
  const statusTextClass = statusBadge?.code === "O" || statusBadge?.code === "D"
    ? "text-red-200"
    : statusBadge?.code === "Q" || statusBadge?.code === "P"
      ? "text-amber-100"
      : "text-emerald-100";
  const seasonRank = card?.season_positional_rank;
  const metricCards = [
    {
      label: "Proj",
      mobileLabel: "Proj",
      value: typeof player.projectedPoints === "number" ? player.projectedPoints.toFixed(1) : "—",
    },
    {
      label: "Positional Rating",
      mobileLabel: "Pos Rating",
      value: formatPlayerCardPositionRank(seasonRank),
    },
    { label: "Class", mobileLabel: "Class", value: card?.about.player_class ?? card?.player.player_class ?? player.playerClass ?? "—" },
    { label: "Status", mobileLabel: "Status", value: playerStatus },
  ];
  return (
    <>
      <button
        type="button"
        aria-label="Close player card"
        onClick={onClose}
        className="absolute right-3 top-3 z-30 inline-flex h-11 w-11 items-center justify-center rounded-md border border-cfb-border-subtle bg-cfb-surface text-cfb-text-secondary transition hover:border-cfb-brand/50 hover:bg-cfb-surface-hover hover:text-white sm:right-4 sm:top-4"
      >
        <X className="h-5 w-5" />
      </button>

      <header data-testid="player-card-header" className={cn("relative min-h-[15.5rem] shrink-0 overflow-hidden border-t-2 border-white/25 bg-gradient-to-r px-5 py-5 sm:min-h-[15.75rem] sm:px-8 sm:py-6", palette.headerBase)}>
        <div
          data-testid="player-card-hero-portrait"
          className="pointer-events-none absolute bottom-0 right-0 z-[5] h-[13rem] w-[11rem] sm:h-[14.5rem] sm:w-[15rem]"
        >
          {headshotUrl && !headshotFailed ? (
            <img
              src={headshotUrl}
              alt={player.name}
              className="h-full w-full object-contain object-bottom opacity-100 [mask-image:linear-gradient(to_right,transparent_0%,black_18%,black_100%)]"
              onError={() => setHeadshotFailed(true)}
            />
          ) : (
            <div className="flex h-full w-full items-end justify-center">
              <UserRound className="mb-4 h-32 w-32 text-white/75 sm:mb-6 sm:h-44 sm:w-44" />
            </div>
          )}
        </div>
        <div data-testid="player-card-identity" className="relative z-10 flex min-h-[12.5rem] min-w-0 flex-col justify-center pr-[10.5rem] text-left sm:min-h-[12.75rem] sm:max-w-[62%] sm:pr-0">
          <p className="cfb-micro-label mb-4 text-white/75 sm:mb-5">{title}</p>
          <div className="min-w-0 max-w-xl">
            <h2 id="player-card-title" className="break-words font-ui text-[1.5rem] font-semibold leading-[1.15] tracking-[-0.025em] text-cfb-text-primary sm:text-[2.75rem]">
              {player.name}
            </h2>
            <p className="mt-2 flex flex-wrap items-center gap-2 text-[11px] font-medium leading-relaxed text-white/85 sm:mt-3 sm:text-sm">
              {position || player.position ? <span data-testid="player-card-position-badge" className={cn("inline-flex rounded-sm border px-2 py-0.5 text-[10px] font-semibold sm:text-xs", palette.pill)}>{position || player.position}</span> : null}
              {card?.about.team ?? player.school ? <span>{position || player.position ? "• " : ""}{card?.about.team ?? player.school}</span> : null}
            </p>
            <div className="mt-2 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs font-bold sm:mt-3 sm:text-sm">
              <PlayerAvailabilityIndicator status={statusSource} showActive={false}>
                <span className={cn("inline-flex items-center gap-1.5", statusTextClass)}>
                  <span data-testid="player-card-status-dot" className={cn("h-1.5 w-1.5 rounded-full", playerAvailabilityDotClass(statusSource))} />
                  {playerStatus}
                </span>
              </PlayerAvailabilityIndicator>
              {card?.about.jersey ? <span className="text-white/70">#{card.about.jersey}</span> : null}
            </div>
          </div>
        </div>
      </header>
      <div data-testid="player-card-metric-rail" className="grid shrink-0 grid-cols-4 divide-x divide-cfb-border-subtle border-y border-cfb-border-subtle bg-cfb-surface">
        {metricCards.map(({ label, mobileLabel, value }) => (
          <div key={label} className="min-w-0 px-2 py-3 text-center sm:px-4 sm:py-4">
            <p className="truncate text-[8px] font-black uppercase tracking-[0.1em] text-white/45 sm:text-[9px] sm:tracking-[0.18em]">
              <span className="sm:hidden" aria-label={label}>{mobileLabel}</span>
              <span className="hidden sm:inline">{label}</span>
            </p>
            <p className={cn("mt-1 break-words font-semibold leading-tight tabular-nums text-white sm:mt-1.5 sm:text-2xl", label === "Class" || label === "Status" ? "text-[10px] min-[375px]:text-[11px]" : "text-[13px]")}>{value}</p>
          </div>
        ))}
      </div>
    </>
  );
}
