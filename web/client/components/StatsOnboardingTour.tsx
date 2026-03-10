import React, { useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearPendingGuide, setCompletedGuide } from "@/lib/onboarding";

type TutorialStep = {
  title: string;
  description: string;
  target?: string;
};

const TUTORIAL_STEPS: TutorialStep[] = [
  {
    title: "Welcome to College Football Fantasy",
    description:
      "This app helps you research teams, compare advanced analytics, track injuries, check standings, and manage your fantasy leagues from one place.",
  },
  {
    target: "#season-selector",
    title: "Choose a Season",
    description: "Switch seasons to compare team stats from different years before you make fantasy decisions.",
  },
  {
    target: "#conference-filter",
    title: "Filter by Conference",
    description: "Use these conference filters to isolate SEC, Big Ten, Big 12, or ACC teams quickly.",
  },
  {
    target: "#team-search",
    title: "Search Any Team",
    description: "Search for a school here to jump straight to that team’s research page.",
  },
  {
    target: "#power4-team-list",
    title: "Browse the Power 4 Team List",
    description: "This list shows all loaded teams in the research center. Click any team to load its analytics.",
  },
  {
    target: "#team-analytics-panel",
    title: "Team Analytics Dashboard",
    description: "This is the main research panel for the selected team, including season context, stats, and standings.",
  },
  {
    target: "#offense-tab",
    title: "Offense Tab",
    description: "Review production, efficiency, and offensive team stats here before projecting fantasy opportunity.",
  },
  {
    target: "#defense-tab",
    title: "Defense Tab",
    description: "Check yards allowed, disruption, and defensive efficiency to evaluate matchup quality.",
  },
  {
    target: "#advanced-tab",
    title: "Advanced Analytics",
    description: "Use deeper metrics like success rate, explosiveness, and EPA-style indicators to find edges.",
  },
  {
    target: "#injuries-tab",
    title: "Injuries Tab",
    description: "Track injured players, expected return timelines, and current status changes for the selected team.",
  },
  {
    target: "#standings-tab",
    title: "Standings Tab",
    description: "Use conference standings and team records here to understand schedule context and team trajectory.",
  },
  {
    title: "You're Ready to Explore",
    description:
      "You now know how to navigate the research center and analyze teams. Use it to make smarter fantasy decisions all season.",
  },
];

type StatsOnboardingTourProps = {
  isOpen: boolean;
  userId: number;
  onClose: () => void;
};

type TooltipPosition = {
  top: number;
  left: number;
  width: number;
};

const PADDING = 12;

export function StatsOnboardingTour({ isOpen, userId, onClose }: StatsOnboardingTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition | null>(null);
  const primaryButtonRef = useRef<HTMLButtonElement | null>(null);

  const step = TUTORIAL_STEPS[currentStep];
  const isFinalStep = currentStep === TUTORIAL_STEPS.length - 1;

  useEffect(() => {
    if (!isOpen) {
      setCurrentStep(0);
      setTargetRect(null);
      setTooltipPosition(null);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setCompletedGuide(userId);
        onClose();
        return;
      }
      if (event.key === "ArrowRight" && currentStep < TUTORIAL_STEPS.length - 1) {
        event.preventDefault();
        setCurrentStep((prev) => prev + 1);
      }
      if (event.key === "ArrowLeft" && currentStep > 0) {
        event.preventDefault();
        setCurrentStep((prev) => prev - 1);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentStep, isOpen, onClose, userId]);

  useLayoutEffect(() => {
    if (!isOpen) return;

    const updateTarget = () => {
      if (!step.target) {
        setTargetRect(null);
        setTooltipPosition(null);
        return;
      }

      const element = document.querySelector(step.target);
      if (!(element instanceof HTMLElement)) {
        setTargetRect(null);
        setTooltipPosition(null);
        return;
      }

      element.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
      if (!element.hasAttribute("tabindex")) {
        element.setAttribute("tabindex", "-1");
      }
      element.focus({ preventScroll: true });

      const rect = element.getBoundingClientRect();
      setTargetRect(rect);

      const width = Math.min(360, window.innerWidth - 32);
      const preferredLeft = rect.left + rect.width / 2 - width / 2;
      const left = Math.max(16, Math.min(preferredLeft, window.innerWidth - width - 16));
      const roomBelow = window.innerHeight - rect.bottom;
      const top = roomBelow > 240
        ? Math.min(rect.bottom + 16, window.innerHeight - 220)
        : Math.max(16, rect.top - 196);

      setTooltipPosition({ top, left, width });
    };

    updateTarget();
    window.addEventListener("resize", updateTarget);
    window.addEventListener("scroll", updateTarget, true);
    return () => {
      window.removeEventListener("resize", updateTarget);
      window.removeEventListener("scroll", updateTarget, true);
    };
  }, [currentStep, isOpen, step.target]);

  useEffect(() => {
    if (!isOpen) return;
    primaryButtonRef.current?.focus();
  }, [currentStep, isOpen]);

  if (!isOpen) return null;

  const finishGuide = () => {
    clearPendingGuide(userId);
    setCompletedGuide(userId);
    onClose();
  };

  return (
    <div
      aria-live="polite"
      aria-modal="true"
      className="fixed inset-0 z-[1200]"
      role="dialog"
    >
      <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-[2px]" />

      {targetRect && (
        <>
          <svg className="pointer-events-auto absolute inset-0 h-full w-full" aria-hidden="true">
            <defs>
              <mask id="tour-mask">
                <rect width="100%" height="100%" fill="white" />
                <rect
                  x={Math.max(0, targetRect.left - PADDING)}
                  y={Math.max(0, targetRect.top - PADDING)}
                  width={Math.min(window.innerWidth, targetRect.width + PADDING * 2)}
                  height={Math.min(window.innerHeight, targetRect.height + PADDING * 2)}
                  rx="20"
                  ry="20"
                  fill="black"
                />
              </mask>
            </defs>
            <rect width="100%" height="100%" fill="rgba(2,6,23,0.82)" mask="url(#tour-mask)" />
          </svg>
          <div
            aria-hidden="true"
            className="pointer-events-none fixed rounded-[24px] border border-primary/80 shadow-[0_0_0_2px_rgba(96,165,250,0.25),0_0_32px_rgba(59,130,246,0.35)]"
            style={{
              left: Math.max(0, targetRect.left - PADDING),
              top: Math.max(0, targetRect.top - PADDING),
              width: targetRect.width + PADDING * 2,
              height: targetRect.height + PADDING * 2,
            }}
          />
        </>
      )}

      <div
        className="fixed z-[1210] rounded-[28px] border border-white/10 bg-[#07101a]/95 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.45)] backdrop-blur-xl"
        style={
          tooltipPosition
            ? { top: tooltipPosition.top, left: tooltipPosition.left, width: tooltipPosition.width }
            : {
                width: Math.min(420, window.innerWidth - 32),
                left: "50%",
                top: "50%",
                transform: "translate(-50%, -50%)",
              }
        }
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.24em] text-primary/80">
              Guided Tour {currentStep + 1}/{TUTORIAL_STEPS.length}
            </p>
            <h2 className="text-2xl font-black italic uppercase tracking-tight text-foreground">
              {step.title}
            </h2>
            <p className="text-sm font-medium leading-6 text-muted-foreground">
              {step.description}
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <Button
              variant="ghost"
              className="h-10 rounded-xl px-4 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground hover:text-foreground"
              onClick={finishGuide}
            >
              End Guide
            </Button>
            <div className="flex items-center gap-2">
              {currentStep > 0 && (
                <Button
                  variant="outline"
                  className="h-10 rounded-xl border-white/10 bg-white/5 px-4 text-[10px] font-black uppercase tracking-[0.18em]"
                  onClick={() => setCurrentStep((prev) => prev - 1)}
                >
                  Back
                </Button>
              )}
              <Button
                ref={primaryButtonRef}
                className="h-10 rounded-xl bg-primary px-5 text-[10px] font-black uppercase tracking-[0.18em] text-primary-foreground"
                onClick={() => {
                  if (isFinalStep) {
                    finishGuide();
                    return;
                  }
                  setCurrentStep((prev) => prev + 1);
                }}
              >
                {isFinalStep ? "End Guide" : "Next"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
