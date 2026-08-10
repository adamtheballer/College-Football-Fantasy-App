/**
 * Shared visual layer for both draft rooms. It is deliberately inert so the
 * restrained broadcast-style surface can never affect draft interactions.
 */
export function DraftRoomVisuals() {
  return (
    <>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_0%,rgba(125,211,252,0.24),transparent_29%),radial-gradient(circle_at_88%_82%,rgba(96,165,250,0.22),transparent_32%),linear-gradient(135deg,#153d63_0%,#1f5b88_48%,#163d66_100%)]" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.13] [background-image:repeating-linear-gradient(0deg,rgba(226,232,240,0.40)_0_1px,transparent_1px_54px),linear-gradient(90deg,transparent_49.8%,rgba(226,232,240,0.32)_50%,transparent_50.2%),repeating-linear-gradient(90deg,transparent_0_67px,rgba(226,232,240,0.18)_67px_69px,transparent_69px_136px)] [background-size:auto_54px,100%_100%,100%_54px]"
      />
      <div aria-hidden="true" className="pointer-events-none absolute -left-32 top-20 h-5 w-[30rem] rotate-[-9deg] bg-gradient-to-r from-transparent via-sky-100/25 to-transparent blur-sm" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-28 bottom-24 h-4 w-[26rem] rotate-[11deg] bg-gradient-to-r from-transparent via-blue-100/20 to-transparent blur-sm" />
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 top-[18rem] h-[24rem] w-[36rem] text-white/[0.11]"
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
  "rounded-[1.75rem] border border-sky-100/24 bg-[#163b60]/[0.90] shadow-[0_14px_34px_rgba(7,27,49,0.30)] backdrop-blur-sm";

export const draftMatteControlClass =
  "border-sky-100/24 bg-[#102f4e]/[0.94] text-slate-100 shadow-[0_8px_20px_rgba(7,27,49,0.28)] backdrop-blur-sm";
