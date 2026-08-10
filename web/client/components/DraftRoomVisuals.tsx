/**
 * Shared visual layer for both draft rooms. It is deliberately inert so the
 * restrained broadcast-style surface can never affect draft interactions.
 */
export function DraftRoomVisuals() {
  return (
    <>
      <div className="pointer-events-none absolute inset-0 bg-[#090b0e]" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:repeating-linear-gradient(0deg,rgba(226,232,240,0.28)_0_1px,transparent_1px_44px)] [background-size:auto_44px]"
      />
    </>
  );
}

export const draftMattePanelClass =
  "rounded-xl border border-white/10 bg-[#15181c] shadow-[0_8px_20px_rgba(0,0,0,0.22)]";

export const draftMatteControlClass =
  "border border-white/10 bg-[#101317] text-slate-100 shadow-[0_4px_12px_rgba(0,0,0,0.18)]";
