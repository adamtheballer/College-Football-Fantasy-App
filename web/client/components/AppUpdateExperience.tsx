import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Bell,
  ChartNoAxesCombined,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleUserRound,
  LayoutDashboard,
  Medal,
  Sparkles,
  Star,
  Trophy,
  UsersRound,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AppReviewCoordinator,
  isReviewSafeRoute,
  reviewScreenIsUsable,
} from "@/components/AppReviewCoordinator";
import { hasPendingGuide } from "@/lib/onboarding";
import {
  hasReviewPresentationBlocker,
  observeReviewPresentation,
} from "@/lib/review-presentation";
import {
  rememberUpdateNotice,
  requestUpdateNotice,
  updateNoticeSeen,
  UPDATE_RELEASE,
  type ReleaseNoticeClaim,
} from "@/lib/release-notice";

export const UPDATE_STEPS = [
  {
    title: "Your next chapter",
    icon: Sparkles,
    description:
      "A fresh look, new ways to compete, and fixes that make managing your team smoother. Take a quick look at what’s new.",
  },
  {
    title: "Weekly Challenges",
    icon: Trophy,
    description:
      "Find five free competitions on Home: Slate 12, Upset Hunter, Fantasy Five, Lock of the Week, and Rivalry Duels. Fresh weekly rounds follow the Matchup rollover. Enter published slates, earn badges, and climb the season leaderboard.",
  },
  {
    title: "A refreshed CFFB",
    icon: LayoutDashboard,
    description:
      "A cleaner dark dashboard, a full-height desktop sidebar, and easier mobile navigation. Player cards keep their position colors with more colorful identity headers.",
  },
  {
    title: "Clearer player graphs",
    icon: ChartNoAxesCombined,
    description:
      "Completed weeks show final fantasy points in blue. The next forecast stays separate, and value history follows the correct weeks. Missing stats are marked Pending until verified.",
  },
  {
    title: "See your latest result",
    icon: Medal,
    description:
      "After a finalized matchup, your updated win count lights up green or your loss count red. The highlight clears at the weekly rollover; older records keep their normal styling.",
  },
  {
    title: "Your name, saved properly",
    icon: CircleUserRound,
    description:
      "Changing your manager name in Settings now saves reliably across screens and sign-ins. If you’re still within the seven-day wait, Settings tells you when you can change it again.",
  },
  {
    title: "Better player information",
    icon: UsersRound,
    description:
      "Player cards show verified game stats, including history from a player’s previous school. Availability indicators appear on player cards, draft boards, rosters, and matchups. Visit Injury Center for the latest reviewed updates.",
  },
  {
    title: "Draft with a clearer board",
    icon: Trophy,
    description:
      "Real and mock drafts share the corrected player ordering and clearer sort controls, so you can compare the available pool consistently.",
  },
  {
    title: "Stay in the loop",
    icon: Bell,
    description:
      "Manage supported league and player alerts in Settings, including iOS notification permission. Big-play alerts have been removed. Delivery follows your preferences and your phone’s notification settings.",
  },
  {
    title: "Help shape CFFB",
    icon: Star,
    description:
      "On iOS, your account has one opportunity for an App Store review request. Apple controls whether the review sheet appears. Thanks for helping us improve the game.",
  },
] as const;

type Props = {
  accountId: number | null;
  managerName: string;
  sessionReady: boolean;
  onboarding: boolean;
  screenKey: string;
  pathname: string;
};

/** One presentation owner sequences onboarding → update walkthrough → App Review. */
export function AppUpdateExperience(props: Props) {
  const {
    accountId,
    managerName,
    sessionReady,
    onboarding,
    pathname,
    screenKey,
  } = props;
  const [resolvedAccount, setResolvedAccount] = useState<number | null>(null);
  const [openAccount, setOpenAccount] = useState<number | null>(null);
  const [step, setStep] = useState(0);
  const nextButton = useRef<HTMLButtonElement>(null);

  useLayoutEffect(() => {
    setOpenAccount(null);
  }, [accountId, sessionReady]);

  useEffect(() => {
    if (accountId === null || !sessionReady) return;
    if (updateNoticeSeen(accountId)) {
      setResolvedAccount(accountId);
      return;
    }
    if (onboarding) return;
    let active = true;
    let requested = false;
    let response: ReleaseNoticeClaim | null = null;
    const check = () => {
      if (
        !active ||
        document.visibilityState !== "visible" ||
        hasPendingGuide(accountId) ||
        !isReviewSafeRoute(pathname) ||
        hasReviewPresentationBlocker() ||
        !reviewScreenIsUsable(document)
      )
        return;
      if (response) {
        if (
          response.authorization === "granted" &&
          !updateNoticeSeen(accountId)
        ) {
          rememberUpdateNotice(accountId);
          setStep(0);
          setOpenAccount(accountId);
        } else rememberUpdateNotice(accountId);
        response = null;
        setResolvedAccount(accountId);
        return;
      }
      if (requested) return;
      requested = true;
      void requestUpdateNotice(accountId)
        .then((result) => {
          if (!active) return;
          if (
            result.account_id !== accountId ||
            result.release_key !== UPDATE_RELEASE
          ) {
            setResolvedAccount(accountId);
            return;
          }
          response = result;
          check(); // Recheck: another modal/permission request may have opened.
        })
        .catch(() => {
          // No fake success and no popup on a failed claim. A later session can
          // retry; an already committed server receipt will never grant twice.
          if (active) setResolvedAccount(accountId);
        });
    };
    const observer = new MutationObserver(check);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: [
        "role",
        "aria-modal",
        "aria-busy",
        "class",
        "style",
        "hidden",
        "data-review-blocking",
      ],
    });
    const removeBlockerListener = observeReviewPresentation(check);
    document.addEventListener("visibilitychange", check);
    document.addEventListener("focusout", check);
    check();
    return () => {
      active = false;
      observer.disconnect();
      removeBlockerListener();
      document.removeEventListener("visibilitychange", check);
      document.removeEventListener("focusout", check);
    };
  }, [accountId, sessionReady, onboarding, pathname, screenKey]);

  const open =
    accountId !== null &&
    accountId === openAccount &&
    sessionReady &&
    !onboarding;
  const current = UPDATE_STEPS[step];
  const Icon = current.icon;
  const finalStep = step === UPDATE_STEPS.length - 1;
  const close = () => setOpenAccount(null);
  return (
    <>
      <AppReviewCoordinator
        {...props}
        onboarding={
          onboarding ||
          open ||
          (sessionReady && accountId !== null && resolvedAccount !== accountId)
        }
      />
      <Dialog
        open={open}
        onOpenChange={(value) => {
          if (!value) close();
        }}
      >
        <DialogContent
          className="max-w-[460px] gap-0 rounded-lg border-border border-t-2 border-t-primary bg-card p-0 sm:p-0"
          data-review-blocking="true"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            nextButton.current?.focus();
          }}
          onInteractOutside={(event) => event.preventDefault()}
        >
          <div className="px-6 pb-5 pt-6 sm:px-7 sm:pt-7">
            <DialogTitle className="cfb-micro-label pr-12 text-primary">
              {UPDATE_RELEASE} Update
            </DialogTitle>
            <div
              className="mt-6 flex h-12 w-12 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary"
              aria-hidden="true"
            >
              <Icon className="h-6 w-6" />
            </div>
            <div
              className="mt-5 min-h-44"
              aria-live="polite"
              aria-atomic="true"
            >
              <h2 className="cfb-section-title break-words pr-1 text-2xl leading-tight [overflow-wrap:anywhere]">
                {step === 0
                  ? `Hi, ${managerName.trim() || "Manager"}.`
                  : current.title}
              </h2>
              {step === 0 && (
                <p className="mt-2 text-sm font-semibold text-foreground">
                  Welcome to CFFB {UPDATE_RELEASE}.
                </p>
              )}
              <DialogDescription className="mt-3 text-sm leading-6 text-muted-foreground">
                {current.description}
              </DialogDescription>
            </div>
            {step === 4 && (
              <p
                className="mt-1 text-lg font-bold"
                aria-label="Record color example: one win, zero losses, zero ties"
              >
                <span className="text-emerald-300">1</span>-0-0{" "}
                <span className="ml-3 text-xs font-normal text-muted-foreground">
                  Latest win
                </span>
              </p>
            )}
            <div
              className="mt-4 flex items-center gap-1.5"
              aria-label={`Update ${step + 1} of ${UPDATE_STEPS.length}`}
            >
              {UPDATE_STEPS.map((item, index) => (
                <span
                  key={item.title}
                  aria-hidden="true"
                  className={`h-1 flex-1 rounded-sm ${index <= step ? "bg-primary" : "bg-muted"}`}
                />
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {step + 1} of {UPDATE_STEPS.length}
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-6 py-4 sm:px-7">
            <Button
              variant="ghost"
              className="px-0 text-muted-foreground"
              onClick={close}
            >
              Skip update
            </Button>
            <div className="flex gap-2">
              {step > 0 && (
                <Button variant="outline" onClick={() => setStep(step - 1)}>
                  <ChevronLeft className="mr-1 h-4 w-4" />
                  Back
                </Button>
              )}
              <Button
                ref={nextButton}
                onClick={() => (finalStep ? close() : setStep(step + 1))}
              >
                {finalStep ? (
                  <>
                    Got it
                    <Check className="ml-2 h-4 w-4" />
                  </>
                ) : (
                  <>
                    Next
                    <ChevronRight className="ml-1 h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
