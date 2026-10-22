import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { trackProductEvent } from "@/lib/product-analytics";
import { Capacitor } from "@capacitor/core";

import { Button } from "@/components/ui/button";
import { clearPendingGuide, setCompletedGuide } from "@/lib/onboarding";

type TourStep = {
  title: string;
  description: string;
  navItem: string;
  target: string;
};

const guidedNavTarget = (navItem: string, fallBackToMore = false) =>
  fallBackToMore
    ? `[data-guide-nav="${navItem}"], [data-guide-nav="MORE"]`
    : `[data-guide-nav="${navItem}"]`;

export const TOUR_STEPS: TourStep[] = [
  {
    navItem: "HOME",
    target: guidedNavTarget("HOME"),
    title: "Your next move",
    description:
      "Home shows open challenges, lineup reminders and verified player leaders. You can skip this guide and explore anytime.",
  },
  {
    navItem: "CHALLENGES",
    target: '[data-guide-challenges], [data-guide-nav="HOME"]',
    title: "Make your first pick",
    description:
      "Choose an open Weekly Challenge. Lock of the Week needs one winner. Review your choice and tap Submit to make it official.",
  },
  {
    navItem: "LEAGUES",
    target: guidedNavTarget("LEAGUES"),
    title: "Your leagues",
    description:
      "Join or create a league, then manage your roster, matchups and waivers. Settings lets you replay this guide whenever you need it.",
  },
];

type AppOnboardingTourProps = {
  isOpen: boolean;
  userId: number;
  onClose: () => void;
  onStepChange?: (navItem: string) => void;
};

type TooltipPosition = {
  top: number;
  left: number;
  width: number;
};

const PADDING = 12;
const NATIVE_TOP_SAFE_AREA_FALLBACK = 59;
const TOOLTIP_RESERVED_HEIGHT = 380;
const NATIVE_BOTTOM_SAFE_AREA = 34;

export const getTourTooltipTop = (targetTop: number, viewportHeight: number, isNativeShell: boolean): number => {
  const minimumTop = isNativeShell ? NATIVE_TOP_SAFE_AREA_FALLBACK : 16;
  const bottomInset = isNativeShell ? NATIVE_BOTTOM_SAFE_AREA : 16;
  // Bottom-nav steps need room for the complete card above the persistent
  // navigation. Reserving the card's height keeps the highlighted tab usable
  // instead of placing the tour controls on top of it.
  return Math.max(minimumTop, Math.min(targetTop, viewportHeight - TOOLTIP_RESERVED_HEIGHT - bottomInset));
};

export function AppOnboardingTour({ isOpen, userId, onClose, onStepChange }: AppOnboardingTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition | null>(null);
  const primaryButtonRef = useRef<HTMLButtonElement | null>(null);
  const activeTargetRef = useRef<HTMLElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  // This dialog is portaled outside AppShell. It needs the same explicit
  // native-status-bar floor as the More drawer instead of relying on the
  // viewport's padding.
  const isNativeShell = Capacitor.isNativePlatform();

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
    if (isOpen) onStepChange?.(TOUR_STEPS[currentStep].navItem);
  }, [currentStep, isOpen, onStepChange]);

  useEffect(() => {
    if (!isOpen) return;
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const originalOverflow = document.body.style.overflow;
    document.body.classList.add("cfb-tour-open");
    document.body.style.overflow = "hidden";
    return () => {
      document.body.classList.remove("cfb-tour-open");
      document.body.style.overflow = originalOverflow;
      returnFocusRef.current?.focus({ preventScroll: true });
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        clearPendingGuide(userId);
        setCompletedGuide(userId);
        void trackProductEvent(userId,"guide_complete");
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

      const element = Array.from(document.querySelectorAll<HTMLElement>(step.target)).find(
        (candidate) => candidate.getClientRects().length > 0,
      );
      if (!(element instanceof HTMLElement)) {
        setTargetRect(null);
        setTooltipPosition(null);
        return;
      }

      element.classList.add("cfb-tour-active-target");
      activeTargetRef.current = element;
      const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

      const sidebarNav = element.closest("aside nav");
      if (sidebarNav instanceof HTMLElement) {
        const containerTop = sidebarNav.scrollTop;
        const containerBottom = containerTop + sidebarNav.clientHeight;
        const elementTop = element.offsetTop;
        const elementBottom = elementTop + element.offsetHeight;
        const margin = 16;

        if (elementTop < containerTop + margin || elementBottom > containerBottom - margin) {
          const targetTop = Math.max(0, elementTop - sidebarNav.clientHeight * 0.25);
          sidebarNav.scrollTo({ top: targetTop, left: 0, behavior: reducedMotion ? "auto" : "smooth" });
        }
      } else {
        element.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center", inline: "nearest" });
      }

      const rect = element.getBoundingClientRect();
      setTargetRect(rect);

      const width = Math.min(336, window.innerWidth - 32);
      const preferredLeft = rect.right + 20;
      const roomRight = window.innerWidth - rect.right;
      const left = roomRight > width + 24
        ? preferredLeft
        : Math.max(16, Math.min(rect.left - width - 20, window.innerWidth - width - 16));
      const top = getTourTooltipTop(rect.top, window.innerHeight, isNativeShell);

      setTooltipPosition({ top, left, width });
    };

    updateTarget();
    const delayedUpdate = window.setTimeout(updateTarget, 120);
    window.addEventListener("resize", updateTarget);
    window.addEventListener("scroll", updateTarget, true);
    return () => {
      if (activeTargetRef.current) {
        activeTargetRef.current.classList.remove("cfb-tour-active-target");
        activeTargetRef.current = null;
      }
      window.removeEventListener("resize", updateTarget);
      window.removeEventListener("scroll", updateTarget, true);
      window.clearTimeout(delayedUpdate);
    };
  }, [currentStep, isNativeShell, isOpen, step.target]);

  useEffect(() => {
    if (!isOpen) return;
    primaryButtonRef.current?.focus();
  }, [currentStep, isOpen]);

  if (!isOpen) return null;

  const finishGuide = () => {
    clearPendingGuide(userId);
    setCompletedGuide(userId);
    void trackProductEvent(userId,"guide_complete");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[1200]" role="dialog" aria-modal="true" aria-live="polite">
      <div className="absolute inset-0 bg-black/40" />

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
            <rect width="100%" height="100%" fill="rgba(2,6,23,0.30)" mask="url(#app-tour-mask)" />
          </svg>
          <div
            aria-hidden="true"
            className="pointer-events-none fixed rounded-lg border-2 border-primary"
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
        className="fixed z-[1210] max-h-[calc(100dvh-7rem)] overflow-y-auto rounded-lg border border-border bg-card p-5 shadow-lg sm:p-6"
        style={
          tooltipPosition
            ? { top: tooltipPosition.top, left: tooltipPosition.left, width: tooltipPosition.width }
            : {
                width: Math.min(336, window.innerWidth - 32),
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
