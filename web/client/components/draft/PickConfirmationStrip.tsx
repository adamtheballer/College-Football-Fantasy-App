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
      className={cn(
        "absolute inset-x-0 top-full h-[5.75rem] overflow-hidden border-b border-primary/35 bg-gradient-to-r from-[#0b2032] via-cfb-surface-raised to-[#102633] text-foreground shadow-[0_14px_28px_rgba(0,0,0,0.34)] sm:h-20",
        !reduced && (phase === "exit" ? "animate-pick-retract" : "animate-pick-reveal")
      )}
    >
      <div className="mx-auto flex h-full w-full max-w-3xl items-center gap-3 px-4 sm:gap-4 sm:px-6">
        <div aria-hidden="true" className="relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-primary/45 bg-primary/10 shadow-[0_0_20px_rgba(67,169,255,0.18)] sm:h-[4.25rem] sm:w-[4.25rem]">
          {pick.imageUrl && !brokenImage
            ? <img src={pick.imageUrl} alt="" className="h-full w-full object-cover object-top" onError={() => setBrokenImage(true)} />
            : <UserRound className="h-8 w-8 text-primary/90 sm:h-9 sm:w-9" />}
          <span className="absolute bottom-1 right-1 rounded-md border border-cfb-surface-raised bg-primary px-1.5 py-0.5 text-[8px] font-black leading-none text-slate-950 shadow-sm">#{pick.number}</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[9px] font-black uppercase tracking-[0.18em] text-primary sm:text-[10px]">{pick.auto ? "Auto-pick confirmed" : "Pick confirmed"}</p>
          <p className="mt-0.5 truncate text-lg font-black leading-tight tracking-tight sm:text-xl">{pick.name}</p>
          <p className="mt-1 truncate text-xs font-bold text-muted-foreground">{pick.position} <span aria-hidden="true">·</span> {pick.school}</p>
        </div>
        <div aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 sm:h-11 sm:w-11">
          <CheckCircle2 className="h-5 w-5 text-primary sm:h-6 sm:w-6" />
        </div>
        <span className="sr-only">Selection confirmed.</span>
      </div>
    </div>
  );
}

export function PickConfirmationStrip({ pick, onFinish, lastPick }: Props) {
  return (
    <div
      data-testid="pick-context-strip"
      className={cn(
        "pointer-events-none fixed inset-x-0 top-0 z-[1260] h-10 overflow-visible border-b border-cfb-border-subtle/80 bg-cfb-surface/96 shadow-[0_6px_18px_rgba(0,0,0,0.2)] backdrop-blur-sm"
      )}
    >
      <div className="flex h-full items-center justify-center gap-1 px-4 text-xs text-muted-foreground" aria-hidden={Boolean(pick)}>
        {lastPick ? <p className="line-clamp-2 text-center">Last pick <strong className="text-foreground">{lastPick.name}</strong> to {lastPick.team}</p> : <p>Confirmed picks will appear here.</p>}
      </div>
      {pick ? <Announcement key={pick.key} pick={pick} onFinish={onFinish} /> : null}
    </div>
  );
}
