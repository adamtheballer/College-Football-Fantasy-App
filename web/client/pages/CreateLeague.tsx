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
  Minus,
  Plus,
  ShieldCheck,
  Sparkles,
  Trophy,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { PlaybookDecor } from "@/components/fantasy/PlaybookDecor";
import { cn } from "@/lib/utils";
import { apiPost, getStoredAccessToken } from "@/lib/api";
import { createLeagueScoringToApi } from "@/lib/scoringSettings";
import { useAuth } from "@/hooks/use-auth";
import { LeagueCreateResponse } from "@/types/league";

const steps = ["Basics", "Settings", "Draft", "Review"] as const;

const leagueSizes = [4, 6, 8, 10, 12, 14, 16];
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
const tradeReviewOptions = [
  { label: "Commissioner", value: "commissioner" },
  { label: "League Vote", value: "league_vote" },
  { label: "None", value: "none" },
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

type RosterSlotKey = "QB" | "RB" | "WR" | "TE" | "FLEX" | "SUPERFLEX" | "K" | "BENCH" | "IR";

const defaultRosterSlots: Record<RosterSlotKey, number> = {
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

const rosterSlotControls: Array<{
  key: RosterSlotKey;
  label: string;
  min: number;
  max: number;
  helper: string;
}> = [
  { key: "QB", label: "QB", min: 1, max: 3, helper: "Starting quarterbacks" },
  { key: "RB", label: "RB", min: 1, max: 5, helper: "Starting running backs" },
  { key: "WR", label: "WR", min: 1, max: 5, helper: "Starting wide receivers" },
  { key: "TE", label: "TE", min: 1, max: 3, helper: "Starting tight ends" },
  { key: "FLEX", label: "FLEX", min: 0, max: 3, helper: "RB / WR / TE slot" },
  { key: "K", label: "K", min: 1, max: 2, helper: "Kicker slots" },
  { key: "BENCH", label: "Bench", min: 0, max: 10, helper: "Reserve spots" },
  { key: "IR", label: "IR", min: 0, max: 4, helper: "Injury reserve" },
];

const defaultScoring = {
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

type ScoringKey = keyof typeof defaultScoring;

const scoringControls: Array<{
  key: ScoringKey;
  label: string;
  step?: string;
  helper: string;
}> = [
  { key: "ppr", label: "Reception", step: "0.5", helper: "Points per reception" },
  { key: "pass_td", label: "Passing TD", helper: "Points per passing touchdown" },
  { key: "pass_yds_per_pt", label: "Pass yards / point", helper: "Passing yards required for 1 point" },
  { key: "rush_yds_per_pt", label: "Rush yards / point", helper: "Rushing yards required for 1 point" },
  { key: "rec_yds_per_pt", label: "Receiving yards / point", helper: "Receiving yards required for 1 point" },
  { key: "rush_td", label: "Rushing TD", helper: "Points per rushing touchdown" },
  { key: "rec_td", label: "Receiving TD", helper: "Points per receiving touchdown" },
  { key: "int", label: "Interception", helper: "Penalty for thrown interceptions" },
  { key: "fumble_lost", label: "Fumble lost", helper: "Penalty for lost fumbles" },
  { key: "fg", label: "Field goal", helper: "Points per made field goal" },
  { key: "xp", label: "Extra point", helper: "Points per made extra point" },
];

const clampNumber = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

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
const smallControlButtonClass =
  "flex h-8 w-8 items-center justify-center rounded-[8px] border border-white/[0.08] bg-[#0B1020] text-[#CBD5E1] transition hover:border-[#60A5FA]/35 hover:bg-[#60A5FA]/10 hover:text-[#F8FAFC] disabled:cursor-not-allowed disabled:opacity-35";

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
  children: React.ReactNode;
  className?: string;
};

function Field({ label, helper, children, className }: FieldProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <Label className={fieldLabelClass}>{label}</Label>
      {children}
      {helper && <p className="text-xs leading-5 text-[#64748B]">{helper}</p>}
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
  const [success, setSuccess] = useState<LeagueCreateResponse | null>(null);

  const detectedTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York";
  const timezone = timezoneOptions.some((option) => option.value === detectedTimezone)
    ? detectedTimezone
    : "America/New_York";
  const currentYear = new Date().getFullYear();

  const [basics, setBasics] = useState({
    name: "Saturday League",
    max_teams: 12,
    is_private: true,
    description: "",
    icon_url: "",
  });

  const [scoring, setScoring] = useState(defaultScoring);

  const [rosterSlots, setRosterSlots] = useState<Record<RosterSlotKey, number>>(defaultRosterSlots);

  const [settings, setSettings] = useState({
    playoff_teams: 4,
    waiver_type: "faab",
    waiver_period_hours: 24,
    waiver_processing_weekday: 1,
    waiver_processing_hour: 8,
    waiver_timezone: timezone,
    faab_starting_budget: 100,
    allow_zero_faab_bids: true,
    reveal_all_waiver_bids: false,
    post_drop_waiver_hours: 24,
    trade_review_type: "commissioner",
  });

  const [draft, setDraft] = useState({
    draft_date: getDefaultDraftDate(),
    draft_time: getDefaultDraftTime(),
    timezone,
    draft_type: "snake",
    pick_timer_seconds: 90,
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

  const canContinue = useMemo(() => {
    if (step === 0) {
      return basics.name.trim().length > 2 && basics.max_teams > 0;
    }
    if (step === 2) {
      return isDraftTimeSafelyInFuture(draftDateTime);
    }
    return true;
  }, [basics.name, basics.max_teams, draftDateTime, step]);

  const nextStepLabel = step < steps.length - 1 ? `Continue to ${steps[step + 1]}` : "Create League";

  const effectiveRosterSlots = useMemo(
    () => ({
      ...rosterSlots,
      SUPERFLEX: 0,
      K: Math.max(1, rosterSlots.K),
    }),
    [rosterSlots],
  );

  const rosterSummary = useMemo(
    () =>
      rosterSlotControls
        .filter((control) => effectiveRosterSlots[control.key] > 0)
        .map((control) => `${control.label} ${effectiveRosterSlots[control.key]}`)
        .join(" · "),
    [effectiveRosterSlots],
  );

  const scoringSummary = useMemo(
    () => `PPR ${scoring.ppr} · Pass TD ${scoring.pass_td} · Rush TD ${scoring.rush_td} · Rec TD ${scoring.rec_td}`,
    [scoring.pass_td, scoring.ppr, scoring.rec_td, scoring.rush_td],
  );

  const updateScoring = (key: ScoringKey, rawValue: number) => {
    setScoring((prev) => ({
      ...prev,
      [key]: Number.isFinite(rawValue) ? rawValue : defaultScoring[key],
    }));
  };

  const updateRosterSlot = (slot: RosterSlotKey, rawValue: number) => {
    const control = rosterSlotControls.find((item) => item.key === slot);
    if (!control) return;

    const nextValue = clampNumber(Number.isFinite(rawValue) ? rawValue : control.min, control.min, control.max);
    setRosterSlots((prev) => ({ ...prev, [slot]: nextValue }));
  };

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

    setLoading(true);
    setError(null);
    try {
      const payload = {
        basics: {
          name: basics.name.trim(),
          season_year: currentYear,
          max_teams: basics.max_teams,
          is_private: basics.is_private,
          description: basics.description || null,
          icon_url: basics.icon_url || null,
        },
        settings: {
          scoring_json: createLeagueScoringToApi(scoring),
          roster_slots_json: effectiveRosterSlots,
          playoff_teams: settings.playoff_teams,
          waiver_type: settings.waiver_type,
          waiver_period_hours: settings.waiver_period_hours,
          waiver_processing_weekday: settings.waiver_processing_weekday,
          waiver_processing_hour: settings.waiver_processing_hour,
          waiver_timezone: settings.waiver_timezone,
          faab_starting_budget: settings.faab_starting_budget,
          allow_zero_faab_bids: settings.allow_zero_faab_bids,
          reveal_all_waiver_bids: settings.reveal_all_waiver_bids,
          post_drop_waiver_hours: settings.post_drop_waiver_hours,
          trade_review_type: settings.trade_review_type,
          superflex_enabled: false,
          kicker_enabled: true,
          defense_enabled: false,
        },
        draft: {
          draft_datetime_utc: draftDateTime.toISOString(),
          timezone: draft.timezone,
          draft_type: draft.draft_type,
          pick_timer_seconds: draft.pick_timer_seconds,
        },
      };
      const response = await apiPost<LeagueCreateResponse>("/leagues", payload);
      if (!response?.league?.id || !response.invite_code || !response.invite_link) {
        throw new Error("League was created, but the API returned an incomplete invite response.");
      }
      queryClient.invalidateQueries({ queryKey: ["leagues"] });
      queryClient.setQueryData(["league", response.league.id], response.league);
      setSuccess(response);
    } catch (err: any) {
      setError(err.message || "Unable to create league.");
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
                  description="Set the public identity, team count, and privacy mode for your league."
                />

                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                  <Field label="League name">
                    <Input
                      value={basics.name}
                      onChange={(e) => setBasics((prev) => ({ ...prev, name: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="League size">
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
                  <Field label="Private league" helper="Only invited managers can join this league.">
                    <div className="flex h-12 items-center gap-3 rounded-[10px] border border-white/[0.08] bg-[#161E2E] px-4">
                      <Switch
                        checked={basics.is_private}
                        onCheckedChange={(value) => setBasics((prev) => ({ ...prev, is_private: value }))}
                        className="data-[state=checked]:bg-[#60A5FA] data-[state=unchecked]:bg-[#334155] focus-visible:ring-[#60A5FA]/30"
                      />
                      <span className="text-sm font-semibold text-[#F8FAFC]">
                        {basics.is_private ? "Invite only" : "Public"}
                      </span>
                    </div>
                  </Field>
                  <Field label="Description (optional)" className="md:col-span-2">
                    <Input
                      value={basics.description}
                      onChange={(e) => setBasics((prev) => ({ ...prev, description: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="League image URL (optional)" className="md:col-span-2">
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
                  description="Customize roster structure and scoring settings that will be persisted with this league."
                />

                <div className="space-y-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <Label className={fieldLabelClass}>Roster format</Label>
                      <p className="mt-2 text-sm leading-6 text-[#94A3B8]">
                        Set starters, flex spots, bench depth, and IR. These settings drive draft length and roster rules.
                      </p>
                    </div>
                    <p className="text-sm font-semibold text-[#60A5FA]">{rosterSummary || "No active slots"}</p>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {rosterSlotControls.map((control) => {
                      const value = effectiveRosterSlots[control.key];

                      return (
                        <div
                          key={control.key}
                          className={cn(
                            "rounded-[14px] border bg-[#161E2E] p-4 transition",
                            "border-white/[0.08] hover:border-[#60A5FA]/25",
                          )}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <span className="text-sm font-bold text-[#F8FAFC]">{control.label}</span>
                              <p className="mt-1 text-xs leading-5 text-[#64748B]">{control.helper}</p>
                            </div>
                            <span className="rounded-full border border-[#60A5FA]/25 bg-[#60A5FA]/10 px-3 py-1 text-sm font-bold text-[#BFDBFE]">
                              {value}
                            </span>
                          </div>
                          <div className="mt-4 flex items-center gap-2">
                            <button
                              type="button"
                              className={smallControlButtonClass}
                              disabled={value <= control.min}
                              onClick={() => updateRosterSlot(control.key, value - 1)}
                              aria-label={`Decrease ${control.label} slots`}
                            >
                              <Minus className="h-4 w-4" />
                            </button>
                            <Input
                              type="number"
                              min={control.min}
                              max={control.max}
                              value={value}
                              onChange={(e) => updateRosterSlot(control.key, Number(e.target.value))}
                              className={cn(inputClass, "h-10 text-center")}
                              aria-label={`${control.label} slots`}
                            />
                            <button
                              type="button"
                              className={smallControlButtonClass}
                              disabled={value >= control.max}
                              onClick={() => updateRosterSlot(control.key, value + 1)}
                              aria-label={`Increase ${control.label} slots`}
                            >
                              <Plus className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                  <Field label="Playoff teams">
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
                  <Field label="Waiver system">
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
                  <Field label="Trade review">
                    <Select
                      value={settings.trade_review_type}
                      onValueChange={(value) => setSettings((prev) => ({ ...prev, trade_review_type: value }))}
                    >
                      <SelectTrigger className={selectTriggerClass}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className={selectContentClass}>
                        {tradeReviewOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value} className="text-sm font-medium">
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>

                <div className="rounded-[1.25rem] border border-sky-300/15 bg-sky-300/[0.04] p-5">
                  <div className="flex flex-col gap-2 border-b border-white/[0.08] pb-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className={fieldLabelClass}>Waiver processing</p>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#94A3B8]">
                        {waiverOptions.find((option) => option.value === settings.waiver_type)?.description}
                      </p>
                    </div>
                    <span className="rounded-full border border-sky-300/25 bg-sky-300/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-sky-100">
                      {settings.waiver_type === "faab" ? "FAAB" : "Priority"}
                    </span>
                  </div>
                  <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
                    <Field label="Processing day">
                      <Select
                        value={String(settings.waiver_processing_weekday)}
                        onValueChange={(value) => setSettings((prev) => ({ ...prev, waiver_processing_weekday: Number(value) }))}
                      >
                        <SelectTrigger className={selectTriggerClass}><SelectValue /></SelectTrigger>
                        <SelectContent className={selectContentClass}>
                          {[
                            [0, "Monday"], [1, "Tuesday"], [2, "Wednesday"], [3, "Thursday"],
                            [4, "Friday"], [5, "Saturday"], [6, "Sunday"],
                          ].map(([value, label]) => <SelectItem key={value} value={String(value)}>{label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field label="Processing time (local hour)">
                      <Input
                        type="number"
                        min="0"
                        max="23"
                        value={settings.waiver_processing_hour}
                        onChange={(event) => setSettings((prev) => ({ ...prev, waiver_processing_hour: clampNumber(Number(event.target.value), 0, 23) }))}
                        className={inputClass}
                      />
                    </Field>
                    <Field label="League time zone">
                      <Select
                        value={settings.waiver_timezone}
                        onValueChange={(value) => setSettings((prev) => ({ ...prev, waiver_timezone: value }))}
                      >
                        <SelectTrigger className={selectTriggerClass}><SelectValue /></SelectTrigger>
                        <SelectContent className={selectContentClass}>
                          {timezoneOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field label="Dropped-player waiver hours" helper="How long a dropped player remains on waivers.">
                      <Input
                        type="number"
                        min="0"
                        max="168"
                        value={settings.post_drop_waiver_hours}
                        onChange={(event) => setSettings((prev) => ({ ...prev, post_drop_waiver_hours: clampNumber(Number(event.target.value), 0, 168) }))}
                        className={inputClass}
                      />
                    </Field>
                    {settings.waiver_type === "faab" ? (
                      <>
                        <Field label="Starting FAAB budget">
                          <Input
                            type="number"
                            min="0"
                            value={settings.faab_starting_budget}
                            onChange={(event) => setSettings((prev) => ({ ...prev, faab_starting_budget: Math.max(0, Number(event.target.value) || 0) }))}
                            className={inputClass}
                          />
                        </Field>
                        <Field label="FAAB options">
                          <div className="grid gap-3 rounded-[10px] border border-white/[0.08] bg-[#161E2E] p-3">
                            <label className="flex items-center justify-between gap-3 text-sm font-medium text-[#CBD5E1]">
                              Allow $0 bids
                              <Switch checked={settings.allow_zero_faab_bids} onCheckedChange={(value) => setSettings((prev) => ({ ...prev, allow_zero_faab_bids: value }))} />
                            </label>
                            <label className="flex items-center justify-between gap-3 text-sm font-medium text-[#CBD5E1]">
                              Reveal all bids after processing
                              <Switch checked={settings.reveal_all_waiver_bids} onCheckedChange={(value) => setSettings((prev) => ({ ...prev, reveal_all_waiver_bids: value }))} />
                            </label>
                          </div>
                        </Field>
                      </>
                    ) : (
                      <div className="rounded-[10px] border border-violet-300/20 bg-violet-300/[0.06] p-4 text-sm leading-6 text-violet-100">
                        <p className="font-bold">Initial priority: Reverse Draft Order</p>
                        <p className="mt-1 text-violet-100/70">The official draft initializes the order. Successful claims move teams to the back.</p>
                      </div>
                    )}
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <Label className={fieldLabelClass}>Scoring settings</Label>
                      <p className="mt-2 text-sm leading-6 text-[#94A3B8]">
                        Customize every scoring value used for projections, matchups, and standings.
                      </p>
                    </div>
                    <p className="text-sm font-semibold text-[#60A5FA]">{scoringSummary}</p>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {scoringControls.map((control) => (
                      <Field key={control.key} label={control.label} helper={control.helper}>
                        <Input
                          type="number"
                          step={control.step ?? "1"}
                          value={scoring[control.key]}
                          onChange={(e) => updateScoring(control.key, Number(e.target.value))}
                          className={inputClass}
                        />
                      </Field>
                    ))}
                  </div>
                </div>

              </div>
            )}

            {step === 2 && (
              <div className="space-y-8">
                <SectionHeader
                  title="Draft Schedule"
                  description="Choose when managers should enter the real league draft room."
                />

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                  <Field label="Draft date">
                    <Input
                      type="date"
                      value={draft.draft_date}
                      onChange={(e) => setDraft((prev) => ({ ...prev, draft_date: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Draft time">
                    <Input
                      type="time"
                      value={draft.draft_time}
                      onChange={(e) => setDraft((prev) => ({ ...prev, draft_time: e.target.value }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Time zone">
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
                  <Field label="Draft type">
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
                  <Field label="Pick timer (seconds)">
                    <Input
                      type="number"
                      value={draft.pick_timer_seconds}
                      onChange={(e) => setDraft((prev) => ({ ...prev, pick_timer_seconds: Number(e.target.value) }))}
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
                  <ReviewItem label="Roster format" value={rosterSummary || "--"} />
                  <ReviewItem label="Scoring" value={scoringSummary} />
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
                disabled={loading}
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
