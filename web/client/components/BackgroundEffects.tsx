import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

// A quiet, static field-night canvas gives the shell a little collegiate
// character without competing with live scores, status colors, or dense data.
// It deliberately contains no animation so it stays comfortable in long
// roster and matchup sessions.
export const collegiateCanvasBackground = [
  "radial-gradient(70% 42% at 50% -12%, rgba(40, 95, 150, 0.15), transparent 72%)",
  "radial-gradient(38% 28% at 100% 22%, rgba(171, 128, 43, 0.045), transparent 76%)",
  "repeating-linear-gradient(118deg, rgba(246, 239, 217, 0.012) 0 1px, transparent 1px 18px)",
  "linear-gradient(180deg, rgb(10, 15, 24) 0%, rgb(7, 10, 15) 42%, rgb(5, 8, 12) 100%)",
].join(", ");

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => (
  <div
    aria-hidden="true"
    data-bg-effects="true"
    className={cn("pointer-events-none fixed inset-0 z-0", className)}
    style={{ background: collegiateCanvasBackground }}
  />
);
