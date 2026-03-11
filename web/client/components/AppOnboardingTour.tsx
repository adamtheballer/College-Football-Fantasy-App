import React, { useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearPendingGuide, setCompletedGuide } from "@/lib/onboarding";

type TourStep = {
  title: string;
  description: string;
  target?: string;
};

const TOUR_STEPS: TourStep[] = [
  {
    title: "Welcome to College Football Fantasy",
    description:
      "This app helps you manage leagues, research teams, track injuries, study projections, and make better lineup decisions all season.",
  },
  {
    target: "#nav-home",
    title: "Home Dashboard",
    description:
      "Start here for your high-level fantasy dashboard, quick league access, and the main hub for the app.",
  },
  {
    target: "#nav-leagues",
    title: "Leagues",
    description:
      "Use Leagues to create, join, and manage your fantasy leagues, view league settings, and prepare for your draft.",
  },
  {
    target: "#nav-roster",
    title: "Roster",
    description:
      "Your roster tab is where you review your players, lineup decisions, projections, and team structure each week.",
  },
  {
    target: "#nav-chats",
    title: "Chats",
    description:
      "Chats keeps league communication in one place so your league stays active before, during, and after games.",
  },
  {
    target: "#nav-watchlist",
    title: "Watchlist",
    description:
      "Use Watchlist to track trade targets, stash candidates, and players you want to monitor before making a move.",
  },
  {
    target: "#nav-waiver-wire",
    title: "Waiver Wire",
    description:
      "Use Waiver Wire to pick up available free agents and add immediate help to your roster each week.",
  },
  {
    target: "#nav-injury-center",
    title: "Injury Center",
    description:
      "Use the injury center to follow fantasy-relevant injuries, status changes, and projected impact on teammates.",
  },
  {
    target: "#nav-alerts",
    title: "Alerts",
    description:
      "Alerts show the most important updates for your players and leagues, including injuries, projection shifts, and big plays.",
  },
  {
    target: "#nav-stats",
    title: "Stats Research Center",
    description:
      "The stats tab is your research hub for Power 4 teams, including offense, defense, advanced analytics, injuries, and standings.",
  },
  {
    target: "#nav-settings",
    title: "Settings",
    description:
      "Customize notifications, league preferences, and account behavior here so the app fits how you play.",
  },
  {
    title: "You're Ready to Explore",
    description:
      "You now know where everything lives. Use the navigation to move through the app and start managing your college fantasy season.",
  },
];

type AppOnboardingTourProps = {
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

export function AppOnboardingTour({ isOpen, userId, onClose }: AppOnboardingTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition | null>(null);
  const primaryButtonRef = useRef<HTMLButtonElement | null>(null);
  const activeTargetRef = useRef<HTMLElement | null>(null);

  const step = TOUR_STEPS[currentStep];
  const isFinalStep = currentStep === TOUR_STEPS.length - 1;

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
        clearPendingGuide(userId);
        setCompletedGuide(userId);
        onClose();
        return;
      }
      if (event.key === "ArrowRight" && currentStep < TOUR_STEPS.length - 1) {
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
      if (activeTargetRef.current) {
        activeTargetRef.current.classList.remove("cfb-tour-active-target");
        activeTargetRef.current = null;
      }

      if (!step.target) {
        window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
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

      element.classList.add("cfb-tour-active-target");
      activeTargetRef.current = element;

      element.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
      if (!element.hasAttribute("tabindex")) {
        element.setAttribute("tabindex", "-1");
      }
      element.focus({ preventScroll: true });

      const rect = element.getBoundingClientRect();
      setTargetRect(rect);

      const width = Math.min(360, window.innerWidth - 32);
      const preferredLeft = rect.right + 20;
      const roomRight = window.innerWidth - rect.right;
      const left = roomRight > width + 24
        ? preferredLeft
        : Math.max(16, Math.min(rect.left - width - 20, window.innerWidth - width - 16));
      const top = Math.max(16, Math.min(rect.top, window.innerHeight - 220));

      setTooltipPosition({ top, left, width });
    };

    updateTarget();
    window.addEventListener("resize", updateTarget);
    window.addEventListener("scroll", updateTarget, true);
    return () => {
      if (activeTargetRef.current) {
        activeTargetRef.current.classList.remove("cfb-tour-active-target");
        activeTargetRef.current = null;
      }
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
    <div className="fixed inset-0 z-[1200]" role="dialog" aria-modal="true" aria-live="polite">
      <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-[1px]" />

      {targetRect && (
        <>
          <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
            <defs>
              <mask id="app-tour-mask">
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
            <rect width="100%" height="100%" fill="rgba(2,6,23,0.42)" mask="url(#app-tour-mask)" />
          </svg>
          <div
            aria-hidden="true"
            className="pointer-events-none fixed rounded-[24px] border border-primary/90 bg-primary/5 shadow-[0_0_0_2px_rgba(96,165,250,0.25),0_0_28px_rgba(59,130,246,0.30)]"
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
        className="fixed z-[1210] rounded-[28px] border border-white/10 bg-[#08121d]/92 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.35)] backdrop-blur-xl"
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
              Guided Tour {currentStep + 1}/{TOUR_STEPS.length}
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
