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
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.045] [background-image:repeating-linear-gradient(0deg,rgba(162,170,183,0.34)_0_1px,transparent_1px_54px),repeating-linear-gradient(90deg,transparent_0_67px,rgba(162,170,183,0.18)_67px_69px,transparent_69px_136px)] [background-size:auto_54px,100%_54px]"
      />
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 top-[18rem] h-[24rem] w-[36rem] text-amber-100/[0.10]"
        fill="none"
        viewBox="0 0 704 480"
      >
        <path d="M54 94 C166 74 192 178 302 160 S438 74 594 112" stroke="currentColor" strokeDasharray="7 12" strokeWidth="2" />
        <path d="M92 318 C204 272 266 388 400 326 S532 228 658 268" stroke="currentColor" strokeDasharray="7 12" strokeWidth="2" />
        <path d="M502 66 l36 20 -28 20" stroke="currentColor" strokeWidth="2" />
        <path d="M566 246 l34 22 -30 18" stroke="currentColor" strokeWidth="2" />
        <circle cx="184" cy="184" r="18" stroke="currentColor" strokeWidth="2" />
        <circle cx="446" cy="326" r="18" stroke="currentColor" strokeWidth="2" />
        <path d="M264 108 l28 28 m0 -28 -28 28 M340 260 l28 28 m0 -28 -28 28" stroke="currentColor" strokeWidth="3" />
        <text x="78" y="240" fill="currentColor" fontSize="38" fontWeight="800">O</text>
        <text x="626" y="162" fill="currentColor" fontSize="38" fontWeight="800">X</text>
      </svg>
    </>
  );
}

export const draftMattePanelClass =
  "rounded-[1.75rem] border border-cfb-border-subtle bg-cfb-surface-raised shadow-[0_14px_34px_rgba(0,0,0,0.28)]";

export const draftMatteControlClass =
  "border-cfb-border-subtle bg-cfb-surface text-cfb-text-primary shadow-[0_8px_20px_rgba(0,0,0,0.22)]";
