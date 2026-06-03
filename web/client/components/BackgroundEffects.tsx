import React from "react";
import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => {
  return (
    <div className={cn("fixed inset-0 pointer-events-none z-[-1] overflow-hidden bg-[#040611]", className)}>
      {/* Dynamic Background Grid */}
      <div
        className="absolute inset-0 opacity-[0.025]"
        style={{ backgroundImage: 'radial-gradient(circle, currentColor 1px, transparent 1px)', backgroundSize: '40px 40px' }}
      />

      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(34,211,238,0.08),transparent_18%),radial-gradient(circle_at_82%_14%,rgba(250,204,21,0.05),transparent_14%),radial-gradient(circle_at_76%_78%,rgba(59,130,246,0.08),transparent_18%),radial-gradient(circle_at_24%_84%,rgba(168,85,247,0.04),transparent_14%)]" />

      {/* VERTICAL GRADUAL BLUE CORE - STATIC */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full pointer-events-none overflow-hidden">
        {/* Main Background Dwindle - Horizontal Dwindle from Center */}
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950/70 via-cyan-500/[0.04] to-slate-950/70" />

        {/* Vertical Core Beam - More Gradual, Less Sharp */}
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[980px] bg-blue-500/[0.045] blur-[220px]" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[420px] bg-cyan-300/[0.07] blur-[150px] mix-blend-screen" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[120px] bg-white/[0.05] blur-[100px]" />
      </div>

      {/* Deep Black edges to anchor the central shine */}
      <div className="absolute top-0 left-0 w-[40%] h-full bg-slate-950/35 blur-[180px]" />
      <div className="absolute top-0 right-0 w-[40%] h-full bg-slate-950/35 blur-[180px]" />

    </div>
  );
};
