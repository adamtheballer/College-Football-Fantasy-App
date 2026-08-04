/**
 * Shared decorative layer for both draft rooms. It is deliberately inert so
 * background field and playbook details can never affect draft interactions.
 */
export function DraftRoomVisuals() {
  return (
    <>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_16%_0%,rgba(180,83,9,0.14),transparent_26%),radial-gradient(circle_at_84%_10%,rgba(22,101,52,0.13),transparent_24%),radial-gradient(circle_at_74%_82%,rgba(109,40,217,0.11),transparent_31%),linear-gradient(135deg,#080d13_0%,#111a22_45%,#15111d_100%)]" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.16] [background-image:repeating-linear-gradient(0deg,rgba(226,232,240,0.38)_0_1px,transparent_1px_54px),linear-gradient(90deg,transparent_49.8%,rgba(226,232,240,0.30)_50%,transparent_50.2%),repeating-linear-gradient(90deg,transparent_0_67px,rgba(226,232,240,0.16)_67px_69px,transparent_69px_136px)] [background-size:auto_54px,100%_100%,100%_54px]"
      />
      <div aria-hidden="true" className="pointer-events-none absolute -left-24 top-28 h-7 w-[38rem] rotate-[-11deg] bg-gradient-to-r from-transparent via-rose-400/40 to-amber-300/10 blur-sm" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-20 top-[26rem] h-6 w-[34rem] rotate-[14deg] bg-gradient-to-r from-transparent via-emerald-300/32 to-sky-300/8 blur-sm" />
      <div aria-hidden="true" className="pointer-events-none absolute bottom-28 left-[18%] h-6 w-[30rem] rotate-[-8deg] bg-gradient-to-r from-transparent via-violet-400/26 to-orange-300/10 blur-sm" />
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute right-0 top-20 hidden h-[30rem] w-[44rem] text-white/10 lg:block"
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
  "rounded-[1.75rem] border border-white/10 bg-[#101923]/92 shadow-[0_14px_34px_rgba(2,6,23,0.34)]";

export const draftMatteControlClass =
  "border-white/14 bg-[#0b121a]/94 text-slate-100 shadow-[0_8px_20px_rgba(2,6,23,0.28)]";
