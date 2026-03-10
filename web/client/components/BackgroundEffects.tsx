import React from "react";
import { cn } from "@/lib/utils";

interface BackgroundEffectsProps {
  className?: string;
}

export const BackgroundEffects = ({ className }: BackgroundEffectsProps) => {
  return (
    <div className={cn("fixed inset-0 pointer-events-none z-[-1] overflow-hidden bg-[#010208]", className)}>
      {/* Dynamic Background Grid */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{ backgroundImage: 'radial-gradient(circle, currentColor 1px, transparent 1px)', backgroundSize: '40px 40px' }}
      />

      {/* VERTICAL GRADUAL BLUE CORE - STATIC */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full pointer-events-none overflow-hidden">
        {/* Main Background Dwindle - Horizontal Dwindle from Center */}
        <div className="absolute inset-0 bg-gradient-to-r from-black/50 via-blue-600/[0.1] to-black/50" />

        {/* Vertical Core Beam - More Gradual, Less Sharp */}
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[1000px] bg-blue-500/[0.04] blur-[220px]" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[500px] bg-sky-400/[0.08] blur-[160px] mix-blend-screen" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[120px] bg-white/[0.08] blur-[100px]" />
      </div>

      {/* Deep Black edges to anchor the central shine */}
      <div className="absolute top-0 left-0 w-[40%] h-full bg-black/30 blur-[180px]" />
      <div className="absolute top-0 right-0 w-[40%] h-full bg-black/30 blur-[180px]" />

    </div>
  );
};
