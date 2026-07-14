import React from "react";
import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => {
  return (
    <div
      data-bg-effects="true"
      className={cn("fixed inset-0 pointer-events-none z-0 overflow-hidden bg-[linear-gradient(135deg,hsl(var(--background-canvas))_0%,#0a1d36_42%,#111943_70%,#1b1038_100%)]", className)}
    >
      {/* Dynamic Background Grid */}
      <div
        className="absolute inset-0 text-cyan-100 opacity-[0.055]"
        style={{ backgroundImage: "radial-gradient(circle, currentColor 1px, transparent 1px)", backgroundSize: "40px 40px" }}
      />
      <div
        className="absolute inset-0 opacity-[0.16]"
        style={{
          backgroundImage:
            "linear-gradient(110deg, transparent 0 47%, rgba(56,189,248,0.16) 47.2% 47.45%, transparent 47.8% 100%), linear-gradient(145deg, transparent 0 63%, rgba(250,204,21,0.13) 63.2% 63.45%, transparent 63.8% 100%)",
          backgroundSize: "280px 280px, 360px 360px",
        }}
      />

      {/* Color fields */}
      <div className="absolute -left-24 top-4 h-[460px] w-[460px] rounded-full bg-cyan-400/20 blur-[120px]" />
      <div className="absolute right-[-90px] top-10 h-[430px] w-[430px] rounded-full bg-blue-500/20 blur-[130px]" />
      <div className="absolute bottom-[-120px] left-[18%] h-[420px] w-[420px] rounded-full bg-sky-400/11 blur-[140px]" />
      <div className="absolute bottom-12 right-[18%] h-[370px] w-[370px] rounded-full bg-fuchsia-500/13 blur-[130px]" />
      <div className="absolute right-[8%] top-[42%] h-[300px] w-[300px] rounded-full bg-amber-300/11 blur-[110px]" />

      {/* Edge paint streaks, kept outside the primary reading area */}
      <div className="absolute -left-20 top-20 h-2 w-72 rotate-[-24deg] rounded-full bg-gradient-to-r from-transparent via-cfb-pink/60 to-cfb-brand/45 blur-[1px]" />
      <div className="absolute -left-14 top-36 h-1.5 w-52 rotate-[-36deg] rounded-full bg-gradient-to-r from-transparent via-cfb-gold/55 to-transparent" />
      <div className="absolute -left-10 top-56 h-1.5 w-64 rotate-[-10deg] rounded-full bg-gradient-to-r from-transparent via-cfb-cyan/45 to-cfb-brand/25" />
      <div className="absolute left-8 top-24 font-display text-3xl font-black text-cfb-cyan/20 rotate-12">×</div>
      <div className="absolute left-24 top-44 font-display text-4xl font-black text-cfb-brand/14 -rotate-12">○</div>

      <div className="absolute -right-24 top-20 h-2 w-80 rotate-[-16deg] rounded-full bg-gradient-to-r from-cfb-cyan/52 via-cfb-brand/46 to-transparent blur-[1px]" />
      <div className="absolute -right-20 top-40 h-1.5 w-60 rotate-[-28deg] rounded-full bg-gradient-to-r from-cfb-pink/55 via-cfb-gold/38 to-transparent" />
      <div className="absolute right-[-34px] top-64 h-2 w-72 rotate-[18deg] rounded-full bg-gradient-to-r from-transparent via-cfb-gold/42 to-cfb-pink/32 blur-[1px]" />
      <div className="absolute right-10 top-28 font-display text-4xl font-black text-cfb-gold/20 -rotate-12">○</div>
      <div className="absolute right-28 top-52 font-display text-3xl font-black text-cfb-cyan/18 rotate-12">×</div>

      <div className="absolute -left-28 bottom-28 h-2 w-80 rotate-[-12deg] rounded-full bg-gradient-to-r from-transparent via-cfb-gold/50 to-cfb-brand/38 blur-[1px]" />
      <div className="absolute -left-16 bottom-16 h-1.5 w-64 rotate-[8deg] rounded-full bg-gradient-to-r from-transparent via-cfb-cyan/46 to-transparent" />
      <div className="absolute left-12 bottom-48 h-1.5 w-56 rotate-[28deg] rounded-full bg-gradient-to-r from-transparent via-cfb-pink/40 to-transparent" />

      <div className="absolute -right-24 bottom-24 h-2 w-80 rotate-[-28deg] rounded-full bg-gradient-to-r from-transparent via-cfb-pink/58 to-cfb-brand/42 blur-[1px]" />
      <div className="absolute -right-12 bottom-14 h-1.5 w-56 rotate-[-10deg] rounded-full bg-gradient-to-r from-cfb-gold/42 via-cfb-cyan/44 to-transparent" />
      <div className="absolute right-20 bottom-48 h-1.5 w-72 rotate-[-34deg] rounded-full bg-gradient-to-r from-transparent via-cfb-brand/36 to-cfb-pink/34" />
      <div className="absolute bottom-24 right-16 font-display text-5xl font-black text-cfb-pink/18">↗</div>

      {/* Football/playbook symbols are low-contrast and anchored to page edges. */}
      <svg className="absolute left-10 top-[38%] h-48 w-48 text-cfb-cyan/12" viewBox="0 0 160 160" fill="none" aria-hidden="true">
        <path d="M22 116 C52 70 88 50 138 34" stroke="currentColor" strokeWidth="7" strokeLinecap="round" />
        <path d="M116 28 L138 34 L128 55" stroke="currentColor" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="43" cy="98" r="12" stroke="currentColor" strokeWidth="6" />
        <path d="M88 58 L109 79 M110 58 L88 80" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
      </svg>
      <svg className="absolute right-10 top-[36%] h-52 w-52 text-cfb-gold/11" viewBox="0 0 180 180" fill="none" aria-hidden="true">
        <path d="M30 132 C44 88 78 66 124 62 C142 60 154 48 162 28" stroke="currentColor" strokeWidth="7" strokeLinecap="round" />
        <path d="M142 29 L162 28 L166 49" stroke="currentColor" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M44 116 L66 138 M68 116 L44 139" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
        <circle cx="116" cy="65" r="13" stroke="currentColor" strokeWidth="6" />
      </svg>
      <svg className="absolute bottom-16 left-[42%] h-40 w-40 text-cfb-pink/10" viewBox="0 0 150 150" fill="none" aria-hidden="true">
        <path d="M20 104 C44 72 71 71 96 47" stroke="currentColor" strokeWidth="7" strokeLinecap="round" />
        <path d="M74 42 L96 47 L88 68" stroke="currentColor" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="32" cy="92" r="10" stroke="currentColor" strokeWidth="5" />
      </svg>

      {/* Vertical core beam */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full pointer-events-none overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950/25 via-sky-500/[0.085] to-indigo-950/30" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[1040px] bg-blue-500/[0.08] blur-[220px]" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[520px] bg-sky-400/[0.11] blur-[160px] mix-blend-screen" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[150px] bg-cyan-100/[0.10] blur-[110px]" />
      </div>

      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(5,12,28,0.08),rgba(5,12,28,0.26))]" />
    </div>
  );
};
