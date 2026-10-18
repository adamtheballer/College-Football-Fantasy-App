import {
  ArrowRight,
  Shield,
  Swords,
  Users,
  Wallet,
  Trophy,
} from "lucide-react";
import { Link } from "react-router-dom";
import { SurfaceCard } from "@/components/fantasy";
import {
  type Challenge,
  FORMATS,
  deadlineText,
  useChallengeState,
} from "@/hooks/use-weekly-challenges";
import {
  type Mode,
  type ExperienceKind,
  experiencePath,
} from "@/hooks/use-challenge-experiences";

export const MODE_PRESENTATION: Record<
  ExperienceKind,
  { cta: string; icon: typeof Trophy; motif: string }
> = {
  fanwars: {
    cta: "Join Fan Wars",
    icon: Swords,
    motif: "FAN ACCURACY · FAN POWER",
  },
  millionaire: {
    cta: "Build Lineup",
    icon: Wallet,
    motif: "$100 VIRTUAL · SIX PLAYERS",
  },
  creator: {
    cta: "Challenge a Creator",
    icon: Users,
    motif: "YOUR PICKS vs. THE EXPERT",
  },
  survivor: {
    cta: "Make Survivor Pick",
    icon: Shield,
    motif: "ONE PICK · NO TEAM REPEATS",
  },
};
export function ChallengeTile({
  challenge: c,
  week,
}: {
  challenge: Challenge;
  week?: number;
}) {
  const state = useChallengeState(c);
  return (
    <Link
      to={experiencePath(c)}
      className="group block rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
    >
      <SurfaceCard className="flex h-full flex-col gap-3 transition-colors group-hover:border-primary/60">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 className="cfb-section-title text-xl">
            {c.experience?.creator
              ? `Beat ${c.experience.creator.name}`
              : c.name}
          </h3>
          <span className="rounded border border-border px-2 py-1 text-xs font-bold">
            {state}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">{FORMATS[c.kind]}</p>
        <p className="text-xs">
          {week ? `Week ${week} · ` : ""}
          {c.participant_count === undefined
            ? ""
            : `${c.participant_count} entrants · `}
          {c.entry?.status === "submitted"
            ? "Entered"
            : c.entry
              ? "Draft saved"
              : "Not entered"}
        </p>
        <p className="text-xs text-muted-foreground">
          Entry deadline: {deadlineText(c.lock_at)}
        </p>
        <span className="mt-auto inline-flex min-h-11 items-center justify-between border-t border-border pt-3 text-sm font-bold text-primary">
          {state === "Open"
            ? c.entry
              ? "Edit Entry"
              : "Enter"
            : state === "Upcoming"
              ? "View Rules"
              : "View Results"}
          <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </span>
      </SurfaceCard>
    </Link>
  );
}
export function ModeTile({
  mode,
  week,
  entered = false,
}: {
  mode: Mode;
  week?: number;
  entered?: boolean;
}) {
  const p = MODE_PRESENTATION[mode.kind];
  const Icon = p.icon;
  return (
    <Link
      to={
        mode.competitions.length === 1
          ? `/weekly-challenges/experiences/${mode.competitions[0]}`
          : `/weekly-challenges/modes/${mode.kind}`
      }
      className="group block rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
    >
      <SurfaceCard className="relative flex h-full flex-col gap-3 overflow-hidden transition-colors group-hover:border-primary/60">
        <div className="flex items-start justify-between gap-3">
          <Icon aria-hidden="true" className="h-8 w-8 text-primary" />
          <span className="rounded border border-border px-2 py-1 text-xs font-bold">
            {mode.state}
          </span>
        </div>
        <p className="cfb-micro-label text-primary">{p.motif}</p>
        <h2 className="cfb-section-title text-xl">{mode.name}</h2>
        <p className="text-sm text-muted-foreground">{mode.description}</p>
        <p className="text-xs">
          {week ? `Week ${week} · ` : ""}
          {mode.participants} entrants · {entered ? "Entered" : "Not entered"}
        </p>
        <p className="text-xs text-muted-foreground">
          {deadlineText(mode.lock_at)}
        </p>
        <span className="mt-auto inline-flex min-h-11 items-center justify-between border-t border-border pt-3 text-sm font-bold text-primary">
          {mode.state === "Open" ? p.cta : "View Competition"}
          <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </span>
      </SurfaceCard>
    </Link>
  );
}
