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

const playbookMarks = [
  { label: "X", className: "left-[58%] top-8" },
  { label: "O", className: "left-[69%] top-14" },
  { label: "X", className: "left-[78%] top-7" },
  { label: "12", className: "left-[87%] bottom-7 text-[18px]" },
];

const sourceLabel = (source?: string | null) => (source ? source.toUpperCase() : "Local");

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
  const metricCards = [
    ["Proj", typeof player.projectedPoints === "number" ? player.projectedPoints.toFixed(1) : "—"],
    ["Rank", player.rankLabel ?? "—"],
    ["Class", card?.about.player_class ?? player.playerClass ?? "—"],
    ["Status", card?.about.status ?? player.status ?? "—"],
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
        className="absolute right-4 top-4 z-30 inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/15 bg-black/25 text-white/75 backdrop-blur transition hover:bg-white/10 hover:text-white"
      >
        <X className="h-5 w-5" />
      </button>

      <header className={cn("relative overflow-hidden px-5 py-6 pr-20 sm:px-8 sm:pr-24", palette.headerBase)}>
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
        <div className="relative z-10 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,440px)] xl:items-start">
          <div className="min-w-0">
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-white/70">{title}</p>
            <div className="mt-4 flex min-w-0 items-center gap-4">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/25 bg-white/10 shadow-[0_16px_34px_rgba(2,6,23,0.28)] sm:h-20 sm:w-20">
                {card?.about.headshot_url ? (
                  <img src={card.about.headshot_url} alt={player.name} className="h-full w-full object-cover" />
                ) : (
                  <div className={cn("flex h-full w-full items-center justify-center bg-gradient-to-b", palette.silhouette)}>
                    <UserRound className="h-9 w-9 text-white/70 sm:h-10 sm:w-10" />
                  </div>
                )}
              </div>
              <div className="min-w-0">
                <h2 className="max-w-2xl break-words text-3xl font-black italic leading-[0.9] tracking-tight text-white sm:text-5xl">
                  {player.name}
                </h2>
                <p className="mt-3 truncate text-xs font-black uppercase tracking-[0.18em] text-white/75">
                  {[card?.about.jersey ? `#${card.about.jersey}` : null, position || player.position, card?.about.team ?? player.school]
                    .filter(Boolean)
                    .join(" • ")}
                </p>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className={cn("rounded-full border px-4 py-2 text-xs font-black", palette.pill)}>{position || "N/A"}</span>
              <span className="rounded-full border border-white/18 bg-black/20 px-4 py-2 text-xs font-black text-white/80">
                {sourceLabel(card?.about.source)} PROFILE
              </span>
              {player.rankLabel ? (
                <span className="rounded-full border border-white/18 bg-black/20 px-4 py-2 text-xs font-black text-white/80">
                  {player.rankLabel}
                </span>
              ) : null}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-2 xl:pt-24 2xl:grid-cols-4">
            {metricCards.map(([label, value]) => (
              <div key={label} className="min-w-0 rounded-2xl border border-white/15 bg-black/25 p-3 backdrop-blur">
                <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/55">{label}</p>
                <p className="mt-2 truncate text-xl font-black tabular-nums text-white">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </header>
    </>
  );
}
