import { cn } from "@/lib/utils";

const symbols = [
  { label: "×", className: "left-8 top-8 text-cfb-cyan rotate-12" },
  { label: "○", className: "right-10 top-8 text-cfb-gold -rotate-12" },
  { label: "+", className: "right-12 bottom-10 text-cfb-brand -rotate-6" },
] as const;

export function PlaybookDecor({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      <div className="absolute -right-24 top-6 h-2 w-56 rotate-[-18deg] rounded-full bg-cfb-pink/40 blur-[1px]" />
      <div className="absolute -left-24 bottom-8 h-2 w-64 rotate-[-12deg] rounded-full bg-cfb-gold/35 blur-[1px]" />
      <div className="absolute -right-10 top-[34%] h-1.5 w-44 rotate-[24deg] rounded-full bg-cfb-cyan/35" />
      {symbols.map((symbol) => (
        <span
          key={`${symbol.label}-${symbol.className}`}
          className={cn("absolute font-display text-2xl font-black opacity-30", symbol.className)}
        >
          {symbol.label}
        </span>
      ))}
      <svg className="absolute bottom-6 right-8 h-10 w-24 text-cfb-pink/28" viewBox="0 0 112 48" fill="none">
        <path
          d="M4 34 C18 4, 26 44, 40 16 S63 6, 72 28 S94 46, 108 10"
          stroke="currentColor"
          strokeWidth="5"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
