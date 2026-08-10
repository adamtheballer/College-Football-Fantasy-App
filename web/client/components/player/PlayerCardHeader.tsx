import type { CSSProperties } from "react";
import { UserRound, X } from "lucide-react";

import type { PlayerCardResponse } from "@/hooks/use-players";
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
  if (!value || value.toUpperCase() === "N_A") return "N/A";
  return value.replace(/_/g, " ");
};

export const resolvePlayerCardStatus = (
  card?: PlayerCardResponse | null,
  contextualStatus?: string | null,
) => formatPlayerCardStatus(card?.current_injury_status ?? card?.about.status ?? contextualStatus);

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
  const playerPills = [
    card?.about.jersey ? `#${card.about.jersey}` : null,
    position || player.position || null,
    card?.about.team ?? player.school ?? null,
  ].filter(Boolean);
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

      <header className={cn("relative shrink-0 overflow-hidden px-4 py-4 pr-14 sm:px-8 sm:py-6 sm:pr-24", palette.headerBase)}>
        <div className="absolute inset-0 opacity-75 mix-blend-screen" style={headerStreakStyle} />
        <div className="absolute inset-0 bg-[repeating-linear-gradient(0deg,transparent_0_28px,rgba(255,255,255,0.07)_29px,transparent_31px_58px)] opacity-30" />
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
        <div className="relative z-10 grid gap-3 sm:gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,440px)] xl:items-end">
          <div className="min-w-0">
            <p className="hidden text-[10px] font-black uppercase tracking-[0.28em] text-white/70 sm:block">{title}</p>
            <div className="flex min-w-0 items-center gap-3 sm:mt-4 sm:gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/25 bg-white/10 shadow-[0_16px_34px_rgba(2,6,23,0.28)] sm:h-20 sm:w-20 sm:rounded-2xl">
                {card?.about.headshot_url ? (
                  <img src={card.about.headshot_url} alt={player.name} className="h-full w-full object-cover" />
                ) : (
                  <div className={cn("flex h-full w-full items-center justify-center bg-gradient-to-b", palette.silhouette)}>
                    <UserRound className="h-7 w-7 text-white/70 sm:h-10 sm:w-10" />
                  </div>
                )}
              </div>
              <div className="min-w-0">
                <h2 className="max-w-2xl break-words text-2xl font-black italic leading-[0.9] tracking-tight text-white sm:text-5xl">
                  {player.name}
                </h2>
                <p className="mt-2 truncate text-[10px] font-black uppercase tracking-[0.15em] text-white/75 sm:mt-3 sm:text-xs sm:tracking-[0.18em]">
                  {[card?.about.jersey ? `#${card.about.jersey}` : null, position || player.position, card?.about.team ?? player.school]
                    .filter(Boolean)
                    .join(" • ")}
                </p>
              </div>
            </div>
            <div className="mt-5 hidden flex-wrap gap-2 sm:flex">
              {playerPills.map((value, index) => (
                <span
                  key={`${value}-${index}`}
                  className={cn(
                    "max-w-full truncate rounded-full border px-4 py-2 text-xs font-black",
                    index === 1 ? palette.pill : "border-white/18 bg-black/20 text-white/85",
                  )}
                >
                  {value}
                </span>
              ))}
            </div>
          </div>
          <div data-testid="player-card-metric-rail" className="grid grid-cols-4 gap-px overflow-hidden rounded-xl border border-white/15 bg-white/10 xl:grid-cols-2 xl:self-end 2xl:grid-cols-4">
            {metricCards.map(({ label, mobileLabel, value }) => (
              <div
                key={label}
                className="flex min-h-[3.8rem] min-w-0 flex-col justify-center bg-black/30 p-2 backdrop-blur sm:min-h-[4.75rem] sm:p-3"
              >
                <p className="truncate text-[8px] font-black uppercase tracking-[0.1em] text-white/55 sm:text-[9px] sm:tracking-[0.18em]">
                  <span className="sm:hidden" aria-label={label}>{mobileLabel}</span>
                  <span className="hidden sm:inline">{label}</span>
                </p>
                <p className="mt-1 truncate text-base font-black tabular-nums text-white sm:mt-2 sm:text-xl">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </header>
    </>
  );
}
