import { useEffect, useState } from "react";
import { CheckCircle2, UserRound } from "lucide-react";
import { PICK_BANNER_MOTION, type ConfirmedDraftPick } from "@/hooks/use-pick-confirmation";
import { cn } from "@/lib/utils";

type Props = {
  pick?: ConfirmedDraftPick;
  onFinish: (key: string) => void;
  lastPick?: { name: string; team: string };
};

function Announcement({ pick, onFinish }: { pick: ConfirmedDraftPick; onFinish: Props["onFinish"] }) {
  const [phase, setPhase] = useState<"enter" | "hold" | "exit">("enter");
  const [brokenImage, setBrokenImage] = useState(false);
  const [reduced] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  useEffect(() => {
    const enter = reduced ? 0 : PICK_BANNER_MOTION.enter;
    const exit = reduced ? 0 : PICK_BANNER_MOTION.exit;
    const holdTimer = window.setTimeout(() => setPhase("hold"), enter);
    const exitTimer = window.setTimeout(() => setPhase("exit"), enter + PICK_BANNER_MOTION.hold);
    const finishTimer = window.setTimeout(() => onFinish(pick.key), enter + PICK_BANNER_MOTION.hold + exit);
    return () => { clearTimeout(holdTimer); clearTimeout(exitTimer); clearTimeout(finishTimer); };
  }, [pick.key, reduced, onFinish]);
  return (
    <div
      role="status" aria-live="polite" aria-atomic="true"
      data-testid="pick-confirmation" data-phase={phase}
      style={{ animationDuration: `${phase === "exit" ? PICK_BANNER_MOTION.exit : PICK_BANNER_MOTION.enter}ms` }}
      className={cn("absolute inset-0 flex items-center gap-3 border-y border-primary/30 bg-cfb-surface-raised px-4 text-foreground", !reduced && (phase === "exit" ? "animate-pick-retract" : "animate-pick-reveal"))}
    >
      <div aria-hidden="true" className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md border border-primary/20 bg-primary/10">
        {pick.imageUrl && !brokenImage
          ? <img src={pick.imageUrl} alt="" className="h-full w-full object-cover" onError={() => setBrokenImage(true)} />
          : <UserRound className="h-8 w-8 text-primary/80" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-bold uppercase tracking-wider text-primary">{pick.auto ? "Auto-pick confirmed" : "You selected"} · Pick {pick.number}</p>
        <p className="line-clamp-2 text-base font-bold leading-tight sm:text-lg">{pick.name}</p>
        <p className="truncate text-xs text-muted-foreground">{pick.position} · {pick.school}</p>
      </div>
      <CheckCircle2 aria-hidden="true" className="h-6 w-6 shrink-0 text-primary" />
      <span className="sr-only">Selection confirmed.</span>
    </div>
  );
}

export function PickConfirmationStrip({ pick, onFinish, lastPick }: Props) {
  return (
    <div data-testid="pick-context-strip" className="sticky top-[calc(env(safe-area-inset-top)+3.5rem)] z-[1260] h-24 shrink-0 overflow-hidden bg-cfb-surface sm:top-28">
      <div className="flex h-full items-center justify-center gap-1 px-4 text-xs text-muted-foreground" aria-hidden={Boolean(pick)}>
        {lastPick ? <p className="line-clamp-2 text-center">Last pick <strong className="text-foreground">{lastPick.name}</strong> to {lastPick.team}</p> : <p>Confirmed picks will appear here.</p>}
      </div>
      {pick ? <Announcement key={pick.key} pick={pick} onFinish={onFinish} /> : null}
    </div>
  );
}
