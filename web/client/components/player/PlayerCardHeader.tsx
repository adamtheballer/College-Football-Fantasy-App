import { useEffect, useState, type CSSProperties } from "react";
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

export const CURRENT_VALUE_RATING_LABEL = "Current Value Rating";

export const formatCurrentValueRating = (value?: number | null) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(0) : "N/A";

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
) => formatPlayerCardStatus(card?.current_injury_status ?? contextualStatus ?? "UNREPORTED");

const playbookMarks = [
  { label: "X", className: "left-[58%] top-8" },
  { label: "O", className: "left-[69%] top-14" },
  { label: "X", className: "left-[78%] top-7" },
  { label: "12", className: "left-[87%] bottom-7 text-[18px]" },
];

export function PlayerCardHeader({
  card,
  currentValue,
  onClose,
  palette,
  player,
  position,
  title,
}: {
  card?: PlayerCardResponse | null;
  currentValue?: number | null;
  onClose: () => void;
  palette: PlayerCardPalette;
  player: PlayerCardModalPlayer;
  position: string;
  title: string;
}) {
  const [headshotFailed, setHeadshotFailed] = useState(false);
  useEffect(() => setHeadshotFailed(false), [card?.about.headshot_url]);
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
    seasonRank
      ? {
          label: "Rank",
          mobileLabel: "Rank",
          value: formatPlayerCardPositionRank(seasonRank),
        }
      : {
          label: CURRENT_VALUE_RATING_LABEL,
          mobileLabel: "Value",
          value: formatCurrentValueRating(currentValue),
        },
    { label: "Class", mobileLabel: "Class", value: card?.about.player_class ?? player.playerClass ?? "—" },
    { label: "Status", mobileLabel: "Status", value: playerStatus },
  ];
  const headerStreakStyle: CSSProperties = {
    backgroundImage: [
      `repeating-linear-gradient(168deg, transparent 0 18px, ${palette.markerA} 19px 27px, transparent 29px 54px)`,
      `linear-gradient(101deg, transparent 0 11%, ${palette.markerB} 11.5% 23%, transparent 24% 100%)`,
      `linear-gradient(116deg, transparent 0 42%, ${palette.markerC} 42.5% 49%, transparent 50% 100%)`,
      "repeating-linear-gradient(90deg, rgba(255,255,255,0.11) 0 1px, transparent 1px 86px)",
    ].join(", "),
    backgroundPosition: "0 0, 0 0, 0 0, 18px 0",
  };

  return (
    <>
      <button
        type="button"
        aria-label="Close player card"
        onClick={onClose}
        className="absolute right-3 top-3 z-30 inline-flex h-9 w-9 items-center justify-center rounded-sm border border-white/15 bg-black/25 text-white/75 backdrop-blur transition hover:bg-white/10 hover:text-white sm:right-4 sm:top-4 sm:h-11 sm:w-11"
      >
        <X className="h-5 w-5" />
      </button>

      <header className={cn("relative min-h-[15.5rem] shrink-0 overflow-hidden bg-gradient-to-br px-5 py-5 sm:min-h-[17.75rem] sm:px-10 sm:py-7", palette.headerBase)}>
        <div className="absolute inset-0 opacity-50 mix-blend-screen" style={headerStreakStyle} />
        <div className="absolute inset-0 bg-[linear-gradient(112deg,rgba(4,8,18,0.14)_0%,transparent_44%,rgba(2,6,23,0.42)_100%)]" />
        <div aria-hidden="true" className="cfb-player-card-grain-layer pointer-events-none absolute inset-0" />
        <div aria-hidden="true" className="cfb-player-card-halftone pointer-events-none absolute inset-0" />
        <div aria-hidden="true" className="cfb-player-card-brush pointer-events-none absolute bottom-4 left-5 sm:bottom-6 sm:left-10" />
        <div
          data-testid="player-card-hero-portrait"
          className="pointer-events-none absolute bottom-0 right-0 z-[5] h-[14.5rem] w-[12.5rem] sm:h-[17.5rem] sm:w-[17.5rem]"
        >
          {card?.about.headshot_url && !headshotFailed ? (
            <img
              src={card.about.headshot_url}
              alt={player.name}
              className="h-full w-full object-contain object-bottom opacity-100 [mask-image:linear-gradient(to_right,transparent_0%,black_18%,black_100%)]"
              onError={() => setHeadshotFailed(true)}
            />
          ) : (
            <div className={cn("flex h-full w-full items-end justify-center bg-gradient-to-l opacity-85 [mask-image:linear-gradient(to_right,transparent_0%,black_18%,black_100%)]", palette.silhouette)}>
              <UserRound className="mb-4 h-32 w-32 text-white/75 sm:mb-6 sm:h-44 sm:w-44" />
            </div>
          )}
        </div>
        <div
          className="pointer-events-none absolute inset-0 hidden text-white/20 [mask-image:linear-gradient(to_right,black_0%,black_58%,transparent_74%)] lg:block"
          aria-hidden="true"
        >
          <div className="absolute left-[40%] top-11 h-px w-36 rotate-[14deg] bg-white/25" />
          <div className="absolute left-[49%] top-[4.25rem] h-px w-32 -rotate-[18deg] bg-white/20" />
          <div className="absolute left-[55%] top-10 h-px w-28 rotate-[25deg] bg-white/15" />
          {playbookMarks.map((mark) => (
            <span
              key={`${mark.label}-${mark.className}`}
              className={cn(
                "absolute -translate-x-[18%] font-black italic leading-none tracking-normal text-white/25",
                mark.label.length > 1 ? "text-base" : "text-3xl",
                mark.className,
              )}
            >
              {mark.label}
            </span>
          ))}
        </div>
        <div aria-hidden="true" className="cfb-player-card-ink-edge pointer-events-none absolute inset-x-0 bottom-0 z-20 h-px" />
        <div data-testid="player-card-identity" className="relative z-10 flex min-h-[12.5rem] min-w-0 flex-col justify-center pr-[10.25rem] text-left sm:min-h-[15rem] sm:max-w-[60%] sm:-translate-y-3 sm:pr-0">
          <p className="mb-3 text-[9px] font-black uppercase tracking-[0.24em] text-white/65 sm:mb-4 sm:text-[10px] sm:tracking-[0.28em]">{title}</p>
          <div className="min-w-0 max-w-xl">
            <h2 id="player-card-title" className="break-words text-[1.8rem] font-black uppercase leading-[0.92] tracking-[-0.035em] text-[#F3F0E7] [text-shadow:0_2px_16px_rgba(2,6,23,0.7)] sm:text-[3.35rem]">
              {player.name}
            </h2>
            <p className="mt-2 truncate text-[10px] font-black uppercase tracking-[0.13em] text-white/80 sm:mt-3 sm:text-xs sm:tracking-[0.18em]">
              {[position || player.position, card?.about.team ?? player.school].filter(Boolean).join("  •  ")}
            </p>
            <div className="mt-2 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-[9px] font-bold sm:mt-3 sm:text-[11px]">
              <PlayerAvailabilityIndicator status={statusSource} showActive={false}>
                <span className={cn("inline-flex items-center gap-1.5", statusTextClass)}>
                  <span data-testid="player-card-status-dot" className={cn("h-1.5 w-1.5 rounded-full", playerAvailabilityDotClass(statusSource))} />
                  {playerStatus}
                </span>
              </PlayerAvailabilityIndicator>
              {card?.about.jersey ? <span className="text-white/70">#{card.about.jersey}</span> : null}
              {!seasonRank && currentValue !== null && currentValue !== undefined ? (
                <span className="text-white/70">Value {formatCurrentValueRating(currentValue)}</span>
              ) : null}
            </div>
          </div>
        </div>
      </header>
      <div data-testid="player-card-metric-rail" className="grid shrink-0 grid-cols-4 divide-x divide-white/10 border-b border-white/10 bg-[#090c11]">
        {metricCards.map(({ label, mobileLabel, value }) => (
          <div key={label} className="min-w-0 px-2 py-3 text-center sm:px-4 sm:py-4">
            <p className="truncate text-[8px] font-black uppercase tracking-[0.1em] text-white/45 sm:text-[9px] sm:tracking-[0.18em]">
              <span className="sm:hidden" aria-label={label}>{mobileLabel}</span>
              <span className="hidden sm:inline">{label}</span>
            </p>
            <p className="mt-1 truncate text-base font-black tabular-nums text-white sm:mt-1.5 sm:text-2xl">{value}</p>
          </div>
        ))}
      </div>
    </>
  );
}
