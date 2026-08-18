import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

// Keep the application canvas neutral. Score colors and selected controls own
// the visual emphasis; the page background must not compete with them.
export const collegiateCanvasBackground = "rgb(9, 11, 15)";

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => (
  <div
    aria-hidden="true"
    data-bg-effects="true"
    className={cn("pointer-events-none fixed inset-0 z-0", className)}
    style={{ background: collegiateCanvasBackground }}
  />
);
