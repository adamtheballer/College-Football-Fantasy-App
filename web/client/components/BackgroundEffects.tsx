import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

// One opaque charcoal canvas across the shell and both draft rooms. Keep
// live data, photos and blue interaction states as the visual focus.
export const collegiateCanvasBackground = "hsl(var(--background-canvas))";

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => (
  <div
    aria-hidden="true"
    data-bg-effects="true"
    className={cn("pointer-events-none fixed inset-0 z-0", className)}
    style={{ background: collegiateCanvasBackground }}
  />
);
