import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

// Keep the application canvas quiet. The old playbook backdrop competed with
// live scores and draft controls on every route.
export const collegiateCanvasBackground = "radial-gradient(circle at 0 0, rgba(251, 191, 36, 0.14), transparent 18%), linear-gradient(135deg, rgb(2, 6, 17), rgb(7, 27, 53) 58%, rgb(2, 7, 19))";

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => (
  <div
    aria-hidden="true"
    data-bg-effects="true"
    className={cn("pointer-events-none fixed inset-0 z-0", className)}
    style={{ background: collegiateCanvasBackground }}
  />
);
