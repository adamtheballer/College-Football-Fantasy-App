import type { CSSProperties } from "react";
import { UserRound, X } from "lucide-react";

import type { PlayerCardResponse } from "@/hooks/use-players";
import { playerAvailabilityDotClass } from "@/lib/playerAvailability";
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

export const formatPlayerCardStatus = (value?: string | null) => {
  if (!value || value.toUpperCase() === "N_A" || value.toUpperCase() === "UNREPORTED") return "NO OFFICIAL REPORT";
  return value.replace(/_/g, " ");
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
  const playerStatus = resolvePlayerCardStatus(card, player.status);
  const statusSource = card?.current_injury_status ?? player.status;
  const metricCards = [
    {
      label: "Proj",
      mobileLabel: "Proj",
      value: typeof player.projectedPoints === "number" ? player.projectedPoints.toFixed(1) : "—",
    },
    {
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
        className="absolute right-3 top-3 z-30 inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-black/25 text-white/75 backdrop-blur transition hover:bg-white/10 hover:text-white sm:right-4 sm:top-4 sm:h-11 sm:w-11"
      >
        <X className="h-5 w-5" />
      </button>

      <header className={cn("relative shrink-0 overflow-hidden bg-gradient-to-br px-4 py-5 pr-14 sm:px-8 sm:py-7 sm:pr-24", palette.headerBase)}>
        <div className="absolute inset-0 opacity-60 mix-blend-screen" style={headerStreakStyle} />
        <div className="absolute inset-0 bg-[linear-gradient(112deg,rgba(4,8,18,0.14)_0%,transparent_44%,rgba(2,6,23,0.42)_100%)]" />
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
        <div className="relative z-10 min-w-0">
          <p className="hidden text-[10px] font-black uppercase tracking-[0.28em] text-white/65 sm:block">{title}</p>
          <div className="flex min-w-0 items-center gap-3 sm:mt-4 sm:gap-5">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/25 bg-white/10 shadow-[0_16px_34px_rgba(2,6,23,0.28)] sm:h-[5.75rem] sm:w-[5.75rem] sm:rounded-[1.6rem]">
                {card?.about.headshot_url ? (
                  <img src={card.about.headshot_url} alt={player.name} className="h-full w-full object-cover" />
                ) : (
                  <div className={cn("flex h-full w-full items-center justify-center bg-gradient-to-b", palette.silhouette)}>
                    <UserRound className="h-8 w-8 text-white/75 sm:h-11 sm:w-11" />
                  </div>
                )}
            </div>
            <div className="min-w-0">
              <h2 className="max-w-2xl break-words text-[1.7rem] font-black italic leading-[0.92] tracking-tight text-white sm:text-5xl">
                {player.name}
              </h2>
              <p className="mt-2 truncate text-[10px] font-black uppercase tracking-[0.15em] text-white/80 sm:mt-3 sm:text-xs sm:tracking-[0.18em]">
                {[position || player.position, card?.about.team ?? player.school].filter(Boolean).join("  |  ")}
              </p>
              <div className="mt-2 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-[9px] font-bold sm:mt-3 sm:text-[11px]">
                <span className="inline-flex items-center gap-1.5 text-emerald-100">
                  <span data-testid="player-card-status-dot" className={cn("h-1.5 w-1.5 rounded-full", playerAvailabilityDotClass(statusSource))} />
                  {playerStatus}
                </span>
                {card?.about.jersey ? <span className="text-white/70">#{card.about.jersey}</span> : null}
                {currentValue !== null && currentValue !== undefined ? <span className="text-white/70">Value {formatCurrentValueRating(currentValue)}</span> : null}
              </div>
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
