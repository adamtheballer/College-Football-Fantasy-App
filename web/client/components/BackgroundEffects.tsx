import React from "react";
import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => {
  return (
    <div className={cn("fixed inset-0 pointer-events-none z-[-1] overflow-hidden bg-[linear-gradient(135deg,#020713_0%,#051426_42%,#090d24_70%,#100720_100%)]", className)}>
      {/* Dynamic Background Grid */}
      <div
        className="absolute inset-0 text-cyan-100 opacity-[0.045]"
        style={{ backgroundImage: "radial-gradient(circle, currentColor 1px, transparent 1px)", backgroundSize: "40px 40px" }}
      />

      {/* Color fields */}
      <div className="absolute -left-24 top-4 h-[460px] w-[460px] rounded-full bg-cyan-400/17 blur-[120px]" />
      <div className="absolute right-[-90px] top-10 h-[430px] w-[430px] rounded-full bg-blue-500/15 blur-[130px]" />
      <div className="absolute bottom-[-120px] left-[18%] h-[420px] w-[420px] rounded-full bg-emerald-400/8 blur-[140px]" />
      <div className="absolute bottom-12 right-[18%] h-[370px] w-[370px] rounded-full bg-fuchsia-500/10 blur-[130px]" />
      <div className="absolute right-[8%] top-[42%] h-[300px] w-[300px] rounded-full bg-amber-300/8 blur-[110px]" />

      {/* Vertical core beam */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full pointer-events-none overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950/45 via-sky-500/[0.065] to-indigo-950/45" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[1040px] bg-blue-500/[0.06] blur-[220px]" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[520px] bg-sky-400/[0.09] blur-[160px] mix-blend-screen" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[150px] bg-cyan-100/[0.08] blur-[110px]" />
      </div>

      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(2,6,23,0.30),rgba(2,6,23,0.58))]" />
    </div>
  );
};
