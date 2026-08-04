/**
 * Shared decorative layer for both draft rooms. It is deliberately inert so
 * background field and playbook details can never affect draft interactions.
 */
export function DraftRoomVisuals() {
  return (
    <>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_0%,rgba(180,83,9,0.07),transparent_24%),radial-gradient(circle_at_88%_82%,rgba(30,64,175,0.05),transparent_28%),linear-gradient(135deg,#080d13_0%,#101820_48%,#0d1319_100%)]" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:repeating-linear-gradient(0deg,rgba(226,232,240,0.38)_0_1px,transparent_1px_54px),linear-gradient(90deg,transparent_49.8%,rgba(226,232,240,0.30)_50%,transparent_50.2%),repeating-linear-gradient(90deg,transparent_0_67px,rgba(226,232,240,0.16)_67px_69px,transparent_69px_136px)] [background-size:auto_54px,100%_100%,100%_54px]"
      />
      <div aria-hidden="true" className="pointer-events-none absolute -left-32 top-20 h-5 w-[30rem] rotate-[-9deg] bg-gradient-to-r from-transparent via-amber-300/14 to-transparent blur-sm" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-28 bottom-24 h-4 w-[26rem] rotate-[11deg] bg-gradient-to-r from-transparent via-slate-200/8 to-transparent blur-sm" />
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 top-[34rem] hidden h-[24rem] w-[36rem] text-white/[0.06] xl:block"
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
  "rounded-[1.75rem] border border-white/12 bg-[#101923] shadow-[0_14px_34px_rgba(2,6,23,0.38)]";

export const draftMatteControlClass =
  "border-white/16 bg-[#0b121a] text-slate-100 shadow-[0_8px_20px_rgba(2,6,23,0.32)]";
