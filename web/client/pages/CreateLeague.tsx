import React, { Component, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Loader2,
  ShieldCheck,
  Sparkles,
  Trophy,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PlaybookDecor } from "@/components/fantasy/PlaybookDecor";
import { cn } from "@/lib/utils";
import { ApiError, apiPost, getStoredAccessToken } from "@/lib/api";
import { createLeagueScoringToApi } from "@/lib/scoringSettings";
import { useAuth } from "@/hooks/use-auth";
import { LeagueCreateResponse } from "@/types/league";

const steps = ["Basics", "Settings", "Draft", "Review"] as const;

export const leagueSizes = [4, 6, 8, 10, 12, 14];
const playoffOptions = [2, 4, 6, 8];
const MIN_DRAFT_LEAD_TIME_MS = 5 * 60 * 1000;
const waiverOptions = [
  {
    label: "FAAB",
    value: "faab",
    description: "Managers submit hidden bids from a season-long budget. The highest valid bid wins.",
  },
  {
    label: "Waiver Priority",
    value: "priority",
    description: "Claims process in waiver order. A successful claim moves the team to the back.",
  },
];
const timezoneOptions = [
  { label: "Eastern Time", value: "America/New_York" },
  { label: "Central Time", value: "America/Chicago" },
  { label: "Mountain Time", value: "America/Denver" },
  { label: "Pacific Time", value: "America/Los_Angeles" },
  { label: "Arizona Time", value: "America/Phoenix" },
  { label: "Alaska Time", value: "America/Anchorage" },
  { label: "Hawaii Time", value: "Pacific/Honolulu" },
  { label: "UTC", value: "UTC" },
];

const standardRosterSlots = {
  QB: 1,
  RB: 2,
  WR: 2,
  TE: 1,
  FLEX: 1,
  SUPERFLEX: 0,
  K: 1,
  BENCH: 5,
  IR: 1,
};

const standardScoring = {
  ppr: 1,
  pass_td: 4,
  pass_yds_per_pt: 25,
  rush_yds_per_pt: 10,
  rec_yds_per_pt: 10,
  rush_td: 6,
  rec_td: 6,
  int: -2,
  fumble_lost: -2,
  fg: 3,
  xp: 1,
};

const standardRosterSummary = "QB 1 · RB 2 · WR 2 · TE 1 · FLEX 1 · K 1 · Bench 5 · IR 1";
const standardScoringSummary = "Standard PPR · 3-point field goals · 1-point extra points";
const managedWaiverSchedule = {
  waiver_period_hours: 24,
  waiver_processing_weekday: 6,
  waiver_processing_hour: 8,
  waiver_timezone: "America/New_York",
  faab_starting_budget: 100,
  allow_zero_faab_bids: true,
  reveal_all_waiver_bids: false,
  post_drop_waiver_hours: 24,
} as const;

const getDefaultDraftDate = () => {
  const now = new Date();
  const draft = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  return draft.toISOString().slice(0, 10);
};

const getDefaultDraftTime = () => "19:00";

const isDraftTimeSafelyInFuture = (draftDateTime: Date | null) =>
  Boolean(
    draftDateTime &&
      Number.isFinite(draftDateTime.getTime()) &&
      draftDateTime.getTime() > Date.now() + MIN_DRAFT_LEAD_TIME_MS
  );

const fieldLabelClass =
  "text-xs font-semibold uppercase tracking-[0.04em] text-[#94A3B8]";
const inputClass =
  "h-12 rounded-[10px] border border-white/[0.08] bg-[#161E2E] px-4 text-[15px] font-medium text-[#F8FAFC] shadow-none backdrop-blur-none placeholder:text-[#64748B] focus-visible:border-[#60A5FA] focus-visible:ring-2 focus-visible:ring-[#60A5FA]/15 focus-visible:ring-offset-0";
const selectTriggerClass =
  "h-12 rounded-[10px] border border-white/[0.08] bg-[#161E2E] px-4 text-[15px] font-medium text-[#F8FAFC] shadow-none backdrop-blur-none focus:ring-2 focus:ring-[#60A5FA]/15 focus-visible:border-[#60A5FA]";
const selectContentClass =
  "rounded-[10px] border border-white/[0.08] bg-[#111827] text-[#F8FAFC] shadow-xl backdrop-blur-none";
const cardClass =
  "rounded-[20px] border border-white/[0.08] bg-[#111827] shadow-[0_12px_32px_rgba(0,0,0,0.18)]";
const primaryButtonClass =
  "h-12 rounded-[10px] bg-[#60A5FA] bg-none px-6 text-sm font-bold text-[#06111F] shadow-none hover:bg-[#7DD3FC] hover:shadow-none focus-visible:ring-[#60A5FA]/30 disabled:bg-[#334155] disabled:text-[#94A3B8]";
const secondaryButtonClass =
  "h-12 rounded-[10px] border border-white/[0.08] bg-[#161E2E] bg-none px-6 text-sm font-semibold text-[#F8FAFC] shadow-none hover:border-white/15 hover:bg-[#1E293B] hover:text-white";

function CreateLeagueBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-[34rem] bg-[radial-gradient(circle_at_14%_10%,rgba(34,211,238,0.2),transparent_27%),radial-gradient(circle_at_78%_18%,rgba(59,130,246,0.22),transparent_26%),linear-gradient(180deg,#10274A_0%,#091426_58%,#070A12_100%)]" />
      <div className="absolute -left-20 top-32 h-3 w-[30rem] rotate-[-17deg] rounded-full bg-[#67E8F9]/25 blur-[1px]" />
      <div className="absolute right-[-8rem] top-44 h-3 w-[32rem] rotate-[20deg] rounded-full bg-[#FBBF24]/30 blur-[1px]" />
      <div className="absolute right-[-5rem] top-64 h-2 w-[24rem] rotate-[20deg] rounded-full bg-[#F43F8E]/40 blur-[1px]" />
      <div className="absolute left-[18%] top-[28rem] h-px w-[64%] bg-gradient-to-r from-transparent via-[#67E8F9]/30 to-transparent" />
      <PlaybookDecor className="opacity-75" />
    </div>
  );
}

function CreateLeagueHero({ currentStep }: { currentStep: number }) {
  return (
    <header className="relative overflow-hidden rounded-[28px] border border-[#60A5FA]/25 bg-[#0C1830]/90 px-6 py-7 shadow-[0_20px_60px_rgba(2,8,23,0.32)] sm:px-8 md:px-10 md:py-9">
      <div aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(116deg,transparent_0%,transparent_46%,rgba(59,130,246,0.16)_46%,transparent_47%,transparent_62%,rgba(251,191,36,0.12)_62%,transparent_63%)]" />
      <div aria-hidden="true" className="absolute -right-8 top-8 h-2 w-48 rotate-[-18deg] rounded-full bg-[#67E8F9]/50" />
      <div aria-hidden="true" className="absolute -right-10 top-14 h-2 w-36 rotate-[-18deg] rounded-full bg-[#F43F8E]/55" />
      <PlaybookDecor className="opacity-55" />

      <div className="relative z-10 grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-end">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-[#67E8F9]/35 bg-[#67E8F9]/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-[#CFFAFE]">
            <Trophy className="h-3.5 w-3.5 text-[#FCD34D]" />
            League Command Center
          </div>
          <p className="mt-5 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-[#7DD3FC]">
            <Zap className="h-3.5 w-3.5" />
            Step {currentStep + 1} of {steps.length} · {steps[currentStep]}
          </p>
          <h1 className="mt-3 max-w-3xl font-display text-4xl font-black italic uppercase leading-[0.9] tracking-[-0.055em] text-[#F8FAFC] sm:text-5xl md:text-6xl">
            Build your <span className="text-[#67E8F9]">league.</span>
          </h1>
          <p className="mt-5 max-w-2xl text-sm leading-6 text-[#B8C7DF] sm:text-base">
            Set the rules, schedule the draft, and send your managers an invite-ready league hub.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <span className="rounded-full border border-[#67E8F9]/25 bg-[#67E8F9]/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.12em] text-[#CFFAFE]">
              Invite only
            </span>
            <span className="rounded-full border border-[#FCD34D]/25 bg-[#FCD34D]/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.12em] text-[#FEF3C7]">
              Live draft room
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 rounded-[22px] border border-white/[0.1] bg-[#081325]/75 p-3 backdrop-blur-sm">
          <div className="rounded-[16px] border border-[#67E8F9]/20 bg-[#67E8F9]/10 p-4">
            <p className={fieldLabelClass}>Current phase</p>
            <p className="mt-2 text-lg font-bold text-[#F8FAFC]">{steps[currentStep]}</p>
          </div>
          <div className="rounded-[16px] border border-[#FCD34D]/20 bg-[#FCD34D]/10 p-4">
            <p className={fieldLabelClass}>Setup</p>
            <p className="mt-2 text-lg font-bold text-[#F8FAFC]">{currentStep + 1}/4</p>
          </div>
          <div className="col-span-2 flex items-center gap-3 rounded-[16px] border border-white/[0.08] bg-[#111E34]/85 px-4 py-3">
            <ShieldCheck className="h-5 w-5 shrink-0 text-[#86EFAC]" />
            <p className="text-xs font-semibold leading-5 text-[#CBD5E1]">Your settings become the source of truth for the whole league.</p>
          </div>
        </div>
      </div>
    </header>
  );
}

function LeagueCreationLoadingOverlay() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="absolute inset-0 z-30 flex min-h-full items-center justify-center bg-[#040A16]/80 px-5 backdrop-blur-sm"
    >
      <div className="relative w-full max-w-md overflow-hidden rounded-[26px] border border-[#67E8F9]/30 bg-[#0C1830] p-7 text-center shadow-[0_30px_80px_rgba(0,0,0,0.45)]">
        <PlaybookDecor className="opacity-60" />
        <div className="relative z-10">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-[18px] border border-[#67E8F9]/30 bg-[#67E8F9]/10">
            <Loader2 className="h-7 w-7 animate-spin text-[#67E8F9]" />
          </div>
          <p className="mt-5 text-xs font-bold uppercase tracking-[0.2em] text-[#7DD3FC]">League setup</p>
          <h2 className="mt-2 font-display text-3xl font-black italic uppercase tracking-[-0.04em] text-[#F8FAFC]">Building your league</h2>
          <p className="mt-3 text-sm leading-6 text-[#B8C7DF]">Saving your rules, draft schedule, and private invite details. Keep this page open.</p>
        </div>
      </div>
    </div>
  );
}

type FieldProps = {
  label: string;
  helper?: string;
  error?: string | null;
  children: React.ReactNode;
  className?: string;
};

function Field({ label, helper, error, children, className }: FieldProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <Label className={fieldLabelClass}>{label}</Label>
      {children}
      {helper && <p className="text-xs leading-5 text-[#64748B]">{helper}</p>}
      {error ? <p role="alert" className="text-xs font-semibold leading-5 text-[#FCA5A5]">{error}</p> : null}
    </div>
  );
}

function Stepper({ currentStep }: { currentStep: number }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
      {steps.map((label, index) => {
        const isActive = index === currentStep;
        const isComplete = index < currentStep;

        return (
          <div
            key={label}
            className={cn(
              "flex items-center gap-3 rounded-[12px] border px-4 py-3 transition-colors",
              isActive
                ? "border-[#60A5FA]/50 bg-[#60A5FA]/10 text-[#F8FAFC]"
                : isComplete
                  ? "border-[#60A5FA]/25 bg-[#60A5FA]/5 text-[#DBEAFE]"
                  : "border-white/[0.08] bg-[#0B1020] text-[#94A3B8]",
            )}
          >
            <span
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold",
                isActive || isComplete
                  ? "border-[#60A5FA] bg-[#60A5FA] text-[#06111F]"
                  : "border-white/[0.12] text-[#94A3B8]",
              )}
            >
              {isComplete ? <Check className="h-3.5 w-3.5" /> : index + 1}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold">{label}</p>
              <p className="text-xs text-[#64748B]">Step {index + 1}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SectionHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="space-y-2">
      <h2 className="text-2xl font-bold tracking-tight text-[#F8FAFC]">{title}</h2>
      {description && <p className="max-w-2xl text-sm leading-6 text-[#94A3B8]">{description}</p>}
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-[14px] border border-white/[0.08] bg-[#161E2E] p-4">
      <p className={fieldLabelClass}>{label}</p>
      <p className="mt-2 text-base font-semibold text-[#F8FAFC]">{value}</p>
    </div>
  );
}

type CreateLeagueErrorBoundaryState = {
  hasError: boolean;
  message: string;
};

class CreateLeagueErrorBoundary extends Component<
  { children: React.ReactNode },
  CreateLeagueErrorBoundaryState
> {
  state: CreateLeagueErrorBoundaryState = {
    hasError: false,
    message: "",
  };

  static getDerivedStateFromError(error: Error): CreateLeagueErrorBoundaryState {
    return {
      hasError: true,
      message: error.message || "The create league page hit an unexpected error.",
    };
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="min-h-full bg-[#070A12] px-6 py-10 text-[#F8FAFC] md:px-10">
        <div className="mx-auto max-w-2xl">
          <div className={cn(cardClass, "p-8 text-center md:p-10")}>
            <p className="text-sm font-semibold text-[#60A5FA]">Create League</p>
            <h1 className="mt-3 text-3xl font-extrabold tracking-[-0.03em]">Something broke on this step</h1>
            <p className="mt-3 text-sm leading-6 text-[#94A3B8]">
              The page recovered instead of going blank. Go back to the leagues page, then reopen Create League.
            </p>
            <p className="mt-4 rounded-[12px] border border-[#EF4444]/30 bg-[#EF4444]/10 px-4 py-3 text-left text-xs font-semibold text-[#FCA5A5]">
              {this.state.message}
            </p>
            <Button
              type="button"
              className={cn(primaryButtonClass, "mt-8")}
              onClick={() => {
                window.location.assign("/leagues");
              }}
            >
              Back to Leagues
            </Button>
          </div>
        </div>
      </div>
    );
  }
}

function formatDraftDateTime(value: Date | null): string {
  if (!value || Number.isNaN(value.getTime())) {
    return "--";
  }

  try {
    return value.toLocaleString();
  } catch {
    return "--";
  }
}

function CreateLeagueForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isLoggedIn } = useAuth();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState<LeagueCreateResponse | null>(null);
  const [standardRulesAcknowledged, setStandardRulesAcknowledged] = useState(false);

  const detectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York";
  const timezone = timezoneOptions.some((option) => option.value === detectedTimezone)
    ? detectedTimezone
    : "America/New_York";
  const currentYear = new Date().getFullYear();

  const [basics, setBasics] = useState({
    name: "Saturday League",
    max_teams: 12,
    description: "",
    icon_url: "",
  });

  const [settings, setSettings] = useState({
    playoff_teams: 4,
    waiver_type: "faab",
  });

  const [draft, setDraft] = useState({
    draft_date: getDefaultDraftDate(),
    draft_time: getDefaultDraftTime(),
    timezone,
    draft_type: "snake",
    draft_order_mode: "random" as "random" | "custom",
    // Preserve an empty field while the commissioner replaces the default.
    // Coercing an empty number input to Number("") previously rendered it as
    // a literal 0, so typing 45 produced the awkward value 045.
    pick_timer_seconds: "90",
  });

  const draftDateTime = useMemo(() => {
    if (!draft.draft_date || !draft.draft_time) return null;
    return new Date(`${draft.draft_date}T${draft.draft_time}:00`);
  }, [draft.draft_date, draft.draft_time]);

  const draftCountdown = useMemo(() => {
    if (!draftDateTime) return null;
    const diffMs = draftDateTime.getTime() - Date.now();
    const days = Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
    return `${days} days`;
  }, [draftDateTime]);

  // Keep the disabled action and its explanation derived from the same clock
  // check. Previously the button was disabled here, but the message was only
  // assigned much later inside handleCreate, which a user can never reach.
  const draftTimeError = useMemo(() => {
    if (!draftDateTime || !Number.isFinite(draftDateTime.getTime())) {
      return "Choose a valid draft date and time.";
    }
    if (!isDraftTimeSafelyInFuture(draftDateTime)) {
      return "Draft time must be at least 5 minutes in the future.";
    }
    return null;
  }, [draftDateTime]);

  const canContinue = useMemo(() => {
    if (step === 0) {
      return basics.name.trim().length > 2 && basics.max_teams > 0;
    }
    if (step === 2) {
      return draftTimeError === null;
    }
    return true;
  }, [basics.name, basics.max_teams, draftTimeError, step]);

  const nextStepLabel = step < steps.length - 1 ? `Continue to ${steps[step + 1]}` : "Create League";

  const updateLeagueSize = (rawValue: number) => {
    setBasics((prev) => ({ ...prev, max_teams: rawValue }));
    setSettings((prev) => ({
      ...prev,
      playoff_teams: Math.min(prev.playoff_teams, rawValue),
    }));
  };

  const handleNext = () => {
    if (!canContinue) return;
    setStep((prev) => Math.min(prev + 1, steps.length - 1));
  };

  const handleBack = () => setStep((prev) => Math.max(prev - 1, 0));

  const handleCreate = async () => {
    if (!isLoggedIn || !getStoredAccessToken()) {
      setError("Your sign-in session expired. Sign in again before creating a league.");
      navigate("/login", { replace: true, state: { from: "/leagues/create" } });
      return;
    }
    if (!draftDateTime || Number.isNaN(draftDateTime.getTime())) {
      setError("Choose a valid draft date and time before creating the league.");
      return;
    }
    if (!isDraftTimeSafelyInFuture(draftDateTime)) {
      setError("Draft time must be at least 5 minutes in the future.");
      return;
    }
    if (!standardRulesAcknowledged) {
      setError("Acknowledge the standard league rules before creating the league.");
      return;
    }

    setLoading(true);
    setError(null);
    setFieldErrors({});
    try {
      const payload = {
        basics: {
          name: basics.name.trim(),
          season_year: currentYear,
          max_teams: basics.max_teams,
          // Public leagues are not a supported product mode. Keep this value
          // explicit for the existing create-league contract and legacy API
          // consumers while the server independently normalizes it as well.
          is_private: true,
          description: basics.description || null,
          icon_url: basics.icon_url || null,
        },
        settings: {
          scoring_json: createLeagueScoringToApi(standardScoring),
          roster_slots_json: standardRosterSlots,
          playoff_teams: settings.playoff_teams,
          waiver_type: settings.waiver_type,
          ...managedWaiverSchedule,
          trade_review_type: "league_vote",
          superflex_enabled: false,
          kicker_enabled: true,
          defense_enabled: false,
        },
        // This field name is part of the existing API contract. The product-facing
        // copy intentionally describes the current alpha rule, not the old beta.
        beta_scoring_acknowledged: standardRulesAcknowledged,
        draft: {
          draft_datetime_utc: draftDateTime.toISOString(),
          timezone: draft.timezone,
          draft_type: draft.draft_type,
          draft_order_mode: draft.draft_order_mode,
          pick_timer_seconds: Number(draft.pick_timer_seconds),
        },
      };
      const response = await apiPost<LeagueCreateResponse>("/leagues", payload);
      if (!response?.league?.id || !response.invite_code || !response.invite_link) {
        throw new Error("League was created, but the API returned an incomplete invite response.");
      }
      queryClient.invalidateQueries({ queryKey: ["leagues"] });
      queryClient.setQueryData(["league", response.league.id], response.league);
      setSuccess(response);
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : "Unable to create league.";
      const field = err instanceof ApiError ? err.field : undefined;
      if (field) {
        setFieldErrors({ [field]: message });
        if (field.startsWith("basics.")) setStep(0);
        else if (field.startsWith("settings.")) setStep(1);
        else if (field.startsWith("draft.")) setStep(2);
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="relative isolate min-h-full overflow-hidden bg-[#070A12] px-6 py-10 text-[#F8FAFC] md:px-10">
        <CreateLeagueBackdrop />
        <div className="relative z-10 mx-auto max-w-2xl">
          <div className={cn(cardClass, "relative overflow-hidden border-[#60A5FA]/20 p-8 text-center md:p-10")}>
            <PlaybookDecor className="opacity-45" />
            <div className="relative z-10">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-[16px] border border-[#67E8F9]/30 bg-[#67E8F9]/10">
                <ShieldCheck className="h-6 w-6 text-[#67E8F9]" />
              </div>
            <p className="text-sm font-semibold text-[#60A5FA]">College Football Fantasy</p>
            <h1 className="mt-3 text-4xl font-extrabold tracking-[-0.03em]">Sign in required</h1>
            <p className="mt-3 text-sm text-[#94A3B8]">You need an account before creating a league.</p>
            <Button type="button" onClick={() => navigate("/login")} className={cn(primaryButtonClass, "mt-8")}>
              Go to Login
            </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="relative isolate min-h-full overflow-hidden bg-[#070A12] px-6 py-8 text-[#F8FAFC] md:px-10">
        <CreateLeagueBackdrop />
        <div className="relative z-10 mx-auto max-w-[1180px]">
          <div className={cn(cardClass, "relative overflow-hidden border-[#60A5FA]/20 p-6 md:p-10")}>
            <PlaybookDecor className="opacity-30" />
            <div className="relative z-10">
            <div className="flex flex-col gap-3 border-b border-white/[0.08] pb-8">
              <div className="flex h-12 w-12 items-center justify-center rounded-[16px] border border-[#67E8F9]/30 bg-[#67E8F9]/10">
                <Sparkles className="h-6 w-6 text-[#67E8F9]" />
              </div>
              <p className="text-sm font-semibold text-[#60A5FA]">League created</p>
              <h1 className="font-display text-4xl font-black italic uppercase tracking-[-0.04em] md:text-5xl">Invite managers</h1>
              <p className="max-w-2xl text-sm leading-6 text-[#94A3B8]">
                Share the invite code or link. Managers can preview the league before joining.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-5 py-8 md:grid-cols-2">
              <div className="rounded-[16px] border border-white/[0.08] bg-[#161E2E] p-5">
                <p className={fieldLabelClass}>Invite code</p>
                <div className="mt-3 flex items-center justify-between gap-4">
                  <span className="text-2xl font-bold tracking-[0.08em] text-[#60A5FA]">{success.invite_code}</span>
                  <Button
                    type="button"
                    variant="outline"
                    className={cn(secondaryButtonClass, "h-10 px-4")}
                    onClick={() => navigator.clipboard.writeText(success.invite_code)}
                  >
                    <Copy className="h-4 w-4" />
                    Copy
                  </Button>
                </div>
              </div>

              <div className="rounded-[16px] border border-white/[0.08] bg-[#161E2E] p-5">
                <p className={fieldLabelClass}>Invite link</p>
                <div className="mt-3 flex items-center justify-between gap-4">
                  <span className="truncate text-sm font-medium text-[#CBD5E1]">{success.invite_link}</span>
                  <Button
                    type="button"
                    variant="outline"
                    className={cn(secondaryButtonClass, "h-10 px-4")}
                    onClick={() => navigator.clipboard.writeText(success.invite_link)}
                  >
                    <Copy className="h-4 w-4" />
                    Copy
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-white/[0.08] pt-6 sm:flex-row sm:items-center sm:justify-between">
              <Button
                type="button"
                variant="outline"
                className={secondaryButtonClass}
                onClick={() => navigate("/leagues")}
              >
                Back to Leagues
              </Button>
              <Button
                type="button"
                className={primaryButtonClass}
                onClick={() => navigate(`/league/${success.league.id}`)}
              >
                Open League Hub
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative isolate min-h-full overflow-hidden bg-[#070A12] px-5 py-6 text-[#F8FAFC] sm:px-8 md:px-10" data-create-step={step}>
      <CreateLeagueBackdrop />
      <div className="relative z-10 mx-auto max-w-[1180px] space-y-7">
        <CreateLeagueHero currentStep={step} />

        <Stepper currentStep={step} />

        {error && (
          <div className="rounded-[12px] border border-[#EF4444]/35 bg-[#EF4444]/10 px-4 py-3 text-sm font-semibold text-[#FCA5A5]">
            {error}
          </div>
        )}

        <section className={cn(cardClass, "relative overflow-hidden border-[#60A5FA]/15")}>
          <div aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#67E8F9] via-[#FCD34D] to-[#F43F8E]" />
          <PlaybookDecor className="opacity-20" />
          <div className="relative z-10 p-5 md:p-8 lg:p-10">
            {step === 0 && (
              <div className="space-y-8">
                <SectionHeader
                  title="League Basics"
                  description="Set your league name, team count, and the details managers will see in their invite."
                />

                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                  <Field label="League name" error={fieldErrors["basics.name"]}>
                    <Input
                      value={basics.name}
                      onChange={(e) => {
                        setBasics((prev) => ({ ...prev, name: e.target.value }));
                        setFieldErrors((current) => ({ ...current, "basics.name": "" }));
                      }}
                      className={inputClass}
                    />
                  </Field>
                  <Field
                    label="League size"
                    helper={basics.max_teams === 14 ? "14-team leagues use a balanced partial round robin before the selected playoff bracket." : undefined}
                    error={fieldErrors["basics.max_teams"]}
                  >
                    <Select
                      value={String(basics.max_teams)}
                      onValueChange={(value) => updateLeagueSize(Number(value))}
                    >
                      <SelectTrigger className={selectTriggerClass}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className={selectContentClass}>
                        {leagueSizes.map((size) => (
                          <SelectItem key={size} value={String(size)} className="text-sm font-medium">
                            {size} Teams
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="Description (optional)" error={fieldErrors["basics.description"]} className="md:col-span-2">
                    <Input
                      value={basics.description}
                      onChange={(e) => setBasics((prev) => ({ ...prev, description: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field
                    label="League image URL (optional)"
                    helper="Paste a public HTTPS image address. Standard image links up to 2,048 characters are supported."
                    error={fieldErrors["basics.icon_url"]}
                    className="md:col-span-2"
                  >
                    <Input
                      value={basics.icon_url}
                      onChange={(e) => setBasics((prev) => ({ ...prev, icon_url: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                </div>
              </div>
            )}

            {step === 1 && (
              <div className="space-y-8">
                <SectionHeader
                  title="League Settings"
                  description="Choose your playoff, waiver, and trade-review rules. Standard roster, scoring, and processing rules apply to every league."
                />

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                  <Field label="Playoff teams" error={fieldErrors["settings.playoff_teams"]}>
                    <Select
                      value={String(settings.playoff_teams)}
                      onValueChange={(value) => setSettings((prev) => ({ ...prev, playoff_teams: Number(value) }))}
                    >
                      <SelectTrigger className={selectTriggerClass}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className={selectContentClass}>
                        {playoffOptions
                          .filter((option) => option <= basics.max_teams)
                          .map((option) => (
                          <SelectItem key={option} value={String(option)} className="text-sm font-medium">
                            {option} Teams
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="Waiver system" error={fieldErrors["settings.waiver_type"]}>
                    <Select
                      value={settings.waiver_type}
                      onValueChange={(value) => setSettings((prev) => ({ ...prev, waiver_type: value }))}
                    >
                      <SelectTrigger className={selectTriggerClass}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className={selectContentClass}>
                        {waiverOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value} className="text-sm font-medium">
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-8">
                <SectionHeader
                  title="Draft Schedule"
                  description="Choose when managers should enter the real league draft room."
                />

                {draftTimeError ? (
                  <div role="alert" className="rounded-[12px] border border-[#EF4444]/35 bg-[#EF4444]/10 px-4 py-3 text-sm font-semibold text-[#FCA5A5]">
                    {draftTimeError}
                  </div>
                ) : null}

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                  <Field label="Draft date" error={fieldErrors["draft.draft_datetime_utc"]}>
                    <Input
                      type="date"
                      value={draft.draft_date}
                      onChange={(e) => setDraft((prev) => ({ ...prev, draft_date: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Draft time" error={fieldErrors["draft.draft_datetime_utc"]}>
                    <Input
                      type="time"
                      value={draft.draft_time}
                      onChange={(e) => setDraft((prev) => ({ ...prev, draft_time: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Time zone" error={fieldErrors["draft.timezone"]}>
                    <Select
                      value={draft.timezone}
                      onValueChange={(value) => setDraft((prev) => ({ ...prev, timezone: value }))}
                    >
                      <SelectTrigger className={selectTriggerClass}>
                        <SelectValue placeholder="Select time zone" />
                      </SelectTrigger>
                      <SelectContent className={selectContentClass}>
                        {timezoneOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value} className="text-sm font-medium">
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                  <Field label="Draft type" error={fieldErrors["draft.draft_type"]}>
                    <Select
                      value={draft.draft_type}
                      onValueChange={(value) => setDraft((prev) => ({ ...prev, draft_type: value }))}
                    >
                      <SelectTrigger className={selectTriggerClass}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className={selectContentClass}>
                        <SelectItem value="snake" className="text-sm font-medium">
                          Snake Draft
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="Draft order" error={fieldErrors["draft.draft_order_mode"]}>
                    <Select
                      value={draft.draft_order_mode}
                      onValueChange={(value: "random" | "custom") =>
                        setDraft((prev) => ({ ...prev, draft_order_mode: value }))
                      }
                    >
                      <SelectTrigger className={selectTriggerClass}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className={selectContentClass}>
                        <SelectItem value="random" className="text-sm font-medium">
                          Random at draft start
                        </SelectItem>
                        <SelectItem value="custom" className="text-sm font-medium">
                          Commissioner sets order
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="mt-2 text-xs font-medium text-[#94A3B8]">
                      {draft.draft_order_mode === "custom"
                        ? "You can assign joined managers to slots in the draft lobby before the draft starts."
                        : "The full order is randomized once when you start the draft."}
                    </p>
                  </Field>
                  <Field label="Pick timer (seconds)" error={fieldErrors["draft.pick_timer_seconds"]}>
                    <Input
                      type="number"
                      min="0"
                      step="1"
                      value={draft.pick_timer_seconds}
                      placeholder="0"
                      onChange={(e) => setDraft((prev) => ({ ...prev, pick_timer_seconds: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Preview">
                    <div className="flex h-12 items-center gap-3 rounded-[10px] border border-white/[0.08] bg-[#161E2E] px-4 text-sm font-semibold text-[#CBD5E1]">
                      <Calendar className="h-4 w-4 text-[#60A5FA]" />
                      {isDraftTimeSafelyInFuture(draftDateTime)
                        ? `Draft starts in ${draftCountdown || "--"}`
                        : "Choose a future draft time"}
                    </div>
                  </Field>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-8">
                <SectionHeader
                  title="Review"
                  description="Confirm the league shell before creating it and generating the invite code."
                />
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <ReviewItem label="League name" value={basics.name} />
                  <ReviewItem label="Teams" value={basics.max_teams} />
                  <ReviewItem label="Draft" value={formatDraftDateTime(draftDateTime)} />
                  <ReviewItem label="Commissioner" value="You" />
                  <ReviewItem label="Roster" value={standardRosterSummary} />
                  <ReviewItem label="Scoring" value={standardScoringSummary} />
                </div>
                <div className="rounded-[16px] border border-[#60A5FA]/30 bg-[#60A5FA]/10 p-5">
                  <div className="flex items-start gap-3">
                    <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-[#60A5FA]" aria-hidden="true" />
                    <p className="text-sm font-bold text-[#DBEAFE]">
                      Standard league rules: Scoring and roster rules are applied to every league and cannot be changed after creation.
                    </p>
                  </div>
                  <label className="mt-4 flex cursor-pointer items-start gap-3 text-sm font-semibold leading-6 text-slate-100">
                    <Checkbox
                      checked={standardRulesAcknowledged}
                      onCheckedChange={(checked) => setStandardRulesAcknowledged(checked === true)}
                      aria-label="I understand that standard scoring and roster rules cannot be changed after league creation."
                    />
                    <span>I understand that standard scoring and roster rules cannot be changed after league creation.</span>
                  </label>
                </div>
              </div>
            )}
          </div>

          <footer className="flex flex-col-reverse gap-3 border-t border-white/[0.08] bg-[#0B1020] px-5 py-4 sm:flex-row sm:items-center sm:justify-between md:px-8 lg:px-10">
            <Button
              type="button"
              variant="outline"
              className={secondaryButtonClass}
              onClick={step === 0 ? () => navigate("/leagues") : handleBack}
            >
              <ChevronLeft className="h-4 w-4" />
              Back
            </Button>
            {step < steps.length - 1 ? (
              <Button
                type="button"
                className={primaryButtonClass}
                disabled={!canContinue}
                onClick={handleNext}
              >
                {nextStepLabel}
                <ChevronRight className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                type="button"
                className={primaryButtonClass}
                onClick={handleCreate}
                disabled={loading || !standardRulesAcknowledged}
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                Create League
              </Button>
            )}
          </footer>
        </section>
      </div>
      {loading ? <LeagueCreationLoadingOverlay /> : null}
    </div>
  );
}

export default function CreateLeague() {
  return (
    <CreateLeagueErrorBoundary>
      <CreateLeagueForm />
    </CreateLeagueErrorBoundary>
  );
}
