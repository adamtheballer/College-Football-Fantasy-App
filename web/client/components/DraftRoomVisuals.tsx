import { collegiateCanvasBackground } from "@/components/BackgroundEffects";

export const draftRoomCanvasBackground = collegiateCanvasBackground;

/**
 * Shared visual layer for both draft rooms. It uses the neutral app canvas;
 * the quiet grid preserves draft context without becoming a competing color
 * layer behind the board.
 */
export function DraftRoomVisuals() {
  return (
    <>
      <div
        data-draft-room-canvas="true"
        className="pointer-events-none absolute inset-0"
        style={{ background: draftRoomCanvasBackground }}
      />
    </>
  );
}

export const draftMattePanelClass =
  "border-y border-cfb-border-subtle bg-cfb-surface-raised shadow-none sm:rounded-md sm:border";

export const draftMatteControlClass =
  "border-cfb-border-subtle bg-cfb-surface text-cfb-text-primary";
