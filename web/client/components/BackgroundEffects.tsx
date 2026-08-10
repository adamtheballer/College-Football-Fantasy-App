import React from "react";
import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => {
  return (
    <div
      data-bg-effects="true"
      className={cn(
        "fixed inset-0 pointer-events-none z-0 overflow-hidden",
        className,
      )}
      style={{
        background:
          "radial-gradient(ellipse at 6% 2%, rgba(251, 191, 36, 0.14), transparent 28%), radial-gradient(ellipse at 94% 6%, rgba(59, 130, 246, 0.16), transparent 31%), radial-gradient(ellipse at 88% 92%, rgba(251, 191, 36, 0.10), transparent 29%), linear-gradient(135deg, #020611 0%, #06152a 42%, #071b35 61%, #020713 100%)",
      }}
    >
      <div className="absolute inset-0 opacity-[0.52]">
        {/* Dynamic Background Grid */}
        <div
          className="absolute inset-0 text-cyan-100 opacity-[0.04]"
          style={{
            backgroundImage:
              "radial-gradient(circle, currentColor 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.12]"
          style={{
            backgroundImage:
              "linear-gradient(110deg, transparent 0 47%, rgba(56,189,248,0.16) 47.2% 47.45%, transparent 47.8% 100%), linear-gradient(145deg, transparent 0 63%, rgba(250,204,21,0.13) 63.2% 63.45%, transparent 63.8% 100%)",
            backgroundSize: "280px 280px, 360px 360px",
          }}
        />

        {/* Color fields */}
        <div className="absolute -left-24 -top-28 h-[490px] w-[490px] rounded-full bg-amber-300/16 blur-[140px]" />
        <div className="absolute right-[-90px] top-10 h-[430px] w-[430px] rounded-full bg-blue-500/16 blur-[145px]" />
        <div className="absolute bottom-[-140px] left-[18%] h-[440px] w-[440px] rounded-full bg-sky-400/[0.075] blur-[155px]" />
        <div className="absolute bottom-[-140px] right-[-90px] h-[420px] w-[420px] rounded-full bg-amber-300/14 blur-[150px]" />
        <div className="absolute right-[8%] top-[42%] h-[300px] w-[300px] rounded-full bg-amber-300/[0.075] blur-[125px]" />

        {/* Sparse gold speckles keep the field feeling collegiate without competing with content. */}
        <div className="absolute left-10 top-16 h-1 w-1 rounded-full bg-amber-100/80 shadow-[0_0_12px_rgba(251,191,36,0.9)]" />
        <div className="absolute left-24 top-28 h-1.5 w-1.5 rounded-full bg-amber-200/70 shadow-[0_0_14px_rgba(251,191,36,0.75)]" />
        <div className="absolute left-16 top-44 h-1 w-1 rounded-full bg-amber-100/65" />
        <div className="absolute right-16 top-24 h-1.5 w-1.5 rounded-full bg-amber-100/75 shadow-[0_0_12px_rgba(251,191,36,0.7)]" />
        <div className="absolute right-32 top-14 h-1 w-1 rounded-full bg-amber-200/80" />
        <div className="absolute bottom-24 right-12 h-1.5 w-1.5 rounded-full bg-amber-100/75 shadow-[0_0_14px_rgba(251,191,36,0.75)]" />
        <div className="absolute bottom-16 right-28 h-1 w-1 rounded-full bg-amber-200/70" />

        {/* Edge paint streaks, kept outside the primary reading area */}
        <div className="absolute -left-20 top-20 h-2 w-72 rotate-[-24deg] rounded-full bg-gradient-to-r from-transparent via-cfb-pink/60 to-cfb-brand/45 blur-[1px]" />
        <div className="absolute -left-14 top-36 h-1.5 w-52 rotate-[-36deg] rounded-full bg-gradient-to-r from-transparent via-cfb-gold/55 to-transparent" />
        <div className="absolute -left-10 top-56 h-1.5 w-64 rotate-[-10deg] rounded-full bg-gradient-to-r from-transparent via-cfb-cyan/45 to-cfb-brand/25" />
        <div className="absolute left-8 top-24 font-display text-3xl font-black text-cfb-cyan/20 rotate-12">
          ×
        </div>
        <div className="absolute left-24 top-44 font-display text-4xl font-black text-cfb-brand/14 -rotate-12">
          ○
        </div>

        <div className="absolute -right-24 top-20 h-2 w-80 rotate-[-16deg] rounded-full bg-gradient-to-r from-cfb-cyan/52 via-cfb-brand/46 to-transparent blur-[1px]" />
        <div className="absolute -right-20 top-40 h-1.5 w-60 rotate-[-28deg] rounded-full bg-gradient-to-r from-cfb-pink/55 via-cfb-gold/38 to-transparent" />
        <div className="absolute right-[-34px] top-64 h-2 w-72 rotate-[18deg] rounded-full bg-gradient-to-r from-transparent via-cfb-gold/42 to-cfb-pink/32 blur-[1px]" />
        <div className="absolute right-10 top-28 font-display text-4xl font-black text-cfb-gold/20 -rotate-12">
          ○
        </div>
        <div className="absolute right-28 top-52 font-display text-3xl font-black text-cfb-cyan/18 rotate-12">
          ×
        </div>

        <div className="absolute -left-28 bottom-28 h-2 w-80 rotate-[-12deg] rounded-full bg-gradient-to-r from-transparent via-cfb-gold/50 to-cfb-brand/38 blur-[1px]" />
        <div className="absolute -left-16 bottom-16 h-1.5 w-64 rotate-[8deg] rounded-full bg-gradient-to-r from-transparent via-cfb-cyan/46 to-transparent" />
        <div className="absolute left-12 bottom-48 h-1.5 w-56 rotate-[28deg] rounded-full bg-gradient-to-r from-transparent via-cfb-pink/40 to-transparent" />

        <div className="absolute -right-24 bottom-24 h-2 w-80 rotate-[-28deg] rounded-full bg-gradient-to-r from-transparent via-cfb-pink/58 to-cfb-brand/42 blur-[1px]" />
        <div className="absolute -right-12 bottom-14 h-1.5 w-56 rotate-[-10deg] rounded-full bg-gradient-to-r from-cfb-gold/42 via-cfb-cyan/44 to-transparent" />
        <div className="absolute right-20 bottom-48 h-1.5 w-72 rotate-[-34deg] rounded-full bg-gradient-to-r from-transparent via-cfb-brand/36 to-cfb-pink/34" />
        <div className="absolute bottom-24 right-16 font-display text-5xl font-black text-cfb-pink/18">
          ↗
        </div>

        {/* Football/playbook symbols are low-contrast and anchored to page edges. */}
        <svg
          className="absolute left-10 top-[38%] h-48 w-48 text-cfb-cyan/[0.085]"
          viewBox="0 0 160 160"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M22 116 C52 70 88 50 138 34"
            stroke="currentColor"
            strokeWidth="7"
            strokeLinecap="round"
          />
          <path
            d="M116 28 L138 34 L128 55"
            stroke="currentColor"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle
            cx="43"
            cy="98"
            r="12"
            stroke="currentColor"
            strokeWidth="6"
          />
          <path
            d="M88 58 L109 79 M110 58 L88 80"
            stroke="currentColor"
            strokeWidth="6"
            strokeLinecap="round"
          />
        </svg>
        <svg
          className="absolute right-10 top-[36%] h-52 w-52 text-cfb-gold/[0.08]"
          viewBox="0 0 180 180"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M30 132 C44 88 78 66 124 62 C142 60 154 48 162 28"
            stroke="currentColor"
            strokeWidth="7"
            strokeLinecap="round"
          />
          <path
            d="M142 29 L162 28 L166 49"
            stroke="currentColor"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M44 116 L66 138 M68 116 L44 139"
            stroke="currentColor"
            strokeWidth="6"
            strokeLinecap="round"
          />
          <circle
            cx="116"
            cy="65"
            r="13"
            stroke="currentColor"
            strokeWidth="6"
          />
        </svg>
        <svg
          className="absolute bottom-16 left-[42%] h-40 w-40 text-cfb-pink/[0.065]"
          viewBox="0 0 150 150"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M20 104 C44 72 71 71 96 47"
            stroke="currentColor"
            strokeWidth="7"
            strokeLinecap="round"
          />
          <path
            d="M74 42 L96 47 L88 68"
            stroke="currentColor"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle
            cx="32"
            cy="92"
            r="10"
            stroke="currentColor"
            strokeWidth="5"
          />
        </svg>

        {/* Vertical core beam */}
        <div className="absolute top-0 left-1/2 h-full w-full -translate-x-1/2 overflow-hidden pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-r from-slate-950/45 via-sky-500/[0.035] to-slate-950/50" />
          <div className="absolute inset-y-0 left-1/2 w-[1040px] -translate-x-1/2 bg-blue-500/[0.045] blur-[220px]" />
          <div className="absolute inset-y-0 left-1/2 w-[520px] -translate-x-1/2 bg-sky-400/[0.055] blur-[180px]" />
        </div>

        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(1,7,18,0.10),rgba(1,7,18,0.44))]" />
      </div>
    </div>
  );
};
