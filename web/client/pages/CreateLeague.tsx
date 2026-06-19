import React, { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Calendar, Check, ChevronLeft, ChevronRight, Copy, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { apiPost } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { LeagueCreateResponse } from "@/types/league";

const steps = ["Basics", "Settings", "Draft", "Review"] as const;

const leagueSizes = [6, 8, 10, 12, 14, 16];
const playoffOptions = [2, 4, 6, 8];
const waiverOptions = [
  { label: "FAAB", value: "faab" },
  { label: "Rolling Waivers", value: "rolling" },
  { label: "Reverse Standings", value: "reverse" },
];
const tradeReviewOptions = [
  { label: "Commissioner", value: "commissioner" },
  { label: "League Vote", value: "league_vote" },
  { label: "None", value: "none" },
];

const getDefaultDraftDate = () => {
  const now = new Date();
  const draft = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  return draft.toISOString().slice(0, 10);
};

const getDefaultDraftTime = () => "19:00";

const fieldLabelClass =
  "text-xs font-semibold uppercase tracking-[0.04em] text-[#94A3B8]";
const inputClass =
  "h-12 rounded-[10px] border border-white/[0.08] bg-[#161E2E] px-4 text-[15px] font-medium text-[#F8FAFC] shadow-none backdrop-blur-none placeholder:text-[#64748B] focus-visible:border-[#22C55E] focus-visible:ring-2 focus-visible:ring-[#22C55E]/15 focus-visible:ring-offset-0";
const selectTriggerClass =
  "h-12 rounded-[10px] border border-white/[0.08] bg-[#161E2E] px-4 text-[15px] font-medium text-[#F8FAFC] shadow-none backdrop-blur-none focus:ring-2 focus:ring-[#22C55E]/15 focus-visible:border-[#22C55E]";
const selectContentClass =
  "rounded-[10px] border border-white/[0.08] bg-[#111827] text-[#F8FAFC] shadow-xl backdrop-blur-none";
const cardClass =
  "rounded-[20px] border border-white/[0.08] bg-[#111827] shadow-[0_12px_32px_rgba(0,0,0,0.18)]";
const primaryButtonClass =
  "h-12 rounded-[10px] bg-[#22C55E] bg-none px-6 text-sm font-bold text-[#04130A] shadow-none hover:bg-[#2FE36C] hover:shadow-none focus-visible:ring-[#22C55E]/30 disabled:bg-[#334155] disabled:text-[#94A3B8]";
const secondaryButtonClass =
  "h-12 rounded-[10px] border border-white/[0.08] bg-[#161E2E] bg-none px-6 text-sm font-semibold text-[#F8FAFC] shadow-none hover:border-white/15 hover:bg-[#1E293B] hover:text-white";

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
                ? "border-[#22C55E]/50 bg-[#22C55E]/10 text-[#F8FAFC]"
                : isComplete
                  ? "border-[#22C55E]/25 bg-[#22C55E]/5 text-[#D1FAE5]"
                  : "border-white/[0.08] bg-[#0B1020] text-[#94A3B8]",
            )}
          >
            <span
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold",
                isActive || isComplete
                  ? "border-[#22C55E] bg-[#22C55E] text-[#04130A]"
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

export default function CreateLeague() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isLoggedIn } = useAuth();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<LeagueCreateResponse | null>(null);

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York";
  const currentYear = new Date().getFullYear();

  const [basics, setBasics] = useState({
    name: "Saturday League",
    season_year: currentYear,
    max_teams: 12,
    is_private: true,
    description: "",
    icon_url: "",
  });

  const [scoring, setScoring] = useState({
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
  });

  const rosterSlots = {
    QB: 1,
    RB: 2,
    WR: 2,
    TE: 1,
    K: 1,
    BENCH: 4,
    IR: 1,
  };

  const [settings, setSettings] = useState({
    playoff_teams: 4,
    waiver_type: "faab",
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
      return !!draft.draft_date && !!draft.draft_time;
    }
    return true;
  }, [basics.name, basics.max_teams, draft.draft_date, draft.draft_time, step]);

  const nextStepLabel = step < steps.length - 1 ? `Continue to ${steps[step + 1]}` : "Create League";

  const handleNext = () => {
    if (!canContinue) return;
    setStep((prev) => Math.min(prev + 1, steps.length - 1));
  };

  const handleBack = () => setStep((prev) => Math.max(prev - 1, 0));

  const handleCreate = async () => {
    if (!draftDateTime || !isLoggedIn) return;
    setLoading(true);
    setError(null);
    try {
      const payload = {
        basics: {
          name: basics.name.trim(),
          season_year: basics.season_year,
          max_teams: basics.max_teams,
          is_private: basics.is_private,
          description: basics.description || null,
          icon_url: basics.icon_url || null,
        },
        settings: {
          scoring_json: scoring,
          roster_slots_json: rosterSlots,
          playoff_teams: settings.playoff_teams,
          waiver_type: settings.waiver_type,
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
      <div className="min-h-full bg-[#070A12] px-6 py-10 text-[#F8FAFC] md:px-10">
        <div className="mx-auto max-w-2xl">
          <div className={cn(cardClass, "p-8 text-center md:p-10")}>
            <p className="text-sm font-semibold text-[#22C55E]">College Football Fantasy</p>
            <h1 className="mt-3 text-4xl font-extrabold tracking-[-0.03em]">Sign in required</h1>
            <p className="mt-3 text-sm text-[#94A3B8]">You need an account before creating a league.</p>
            <Button type="button" onClick={() => navigate("/login")} className={cn(primaryButtonClass, "mt-8")}>
              Go to Login
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-full bg-[#070A12] px-6 py-8 text-[#F8FAFC] md:px-10">
        <div className="mx-auto max-w-[1180px]">
          <div className={cn(cardClass, "p-6 md:p-10")}>
            <div className="flex flex-col gap-3 border-b border-white/[0.08] pb-8">
              <p className="text-sm font-semibold text-[#22C55E]">League created</p>
              <h1 className="text-4xl font-extrabold tracking-[-0.03em] md:text-5xl">Invite managers</h1>
              <p className="max-w-2xl text-sm leading-6 text-[#94A3B8]">
                Share the invite code or link. Managers can preview the league before joining.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-5 py-8 md:grid-cols-2">
              <div className="rounded-[16px] border border-white/[0.08] bg-[#161E2E] p-5">
                <p className={fieldLabelClass}>Invite code</p>
                <div className="mt-3 flex items-center justify-between gap-4">
                  <span className="text-2xl font-bold tracking-[0.08em] text-[#22C55E]">{success.invite_code}</span>
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
    );
  }

  return (
    <div className="min-h-full bg-[#070A12] px-5 py-6 text-[#F8FAFC] sm:px-8 md:px-10" data-create-step={step}>
      <div className="mx-auto max-w-[1180px] space-y-7">
        <header className="space-y-3">
          <p className="text-sm font-semibold text-[#22C55E]">College Football Fantasy</p>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-4xl font-extrabold tracking-[-0.03em] text-[#F8FAFC] md:text-5xl">
                Create League
              </h1>
              <p className="mt-2 text-base text-[#94A3B8]">
                Step {step + 1} of {steps.length} · {steps[step]}
              </p>
            </div>
            <p className="max-w-md text-sm leading-6 text-[#94A3B8]">
              Configure the league shell, scoring, and draft schedule before inviting managers.
            </p>
          </div>
        </header>

        <Stepper currentStep={step} />

        {error && (
          <div className="rounded-[12px] border border-[#EF4444]/35 bg-[#EF4444]/10 px-4 py-3 text-sm font-semibold text-[#FCA5A5]">
            {error}
          </div>
        )}

        <section className={cn(cardClass, "overflow-hidden")}>
          <div className="p-5 md:p-8 lg:p-10">
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
                  <Field label="Season year">
                    <Input
                      type="number"
                      value={basics.season_year}
                      onChange={(e) => setBasics((prev) => ({ ...prev, season_year: Number(e.target.value) }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="League size">
                    <Select
                      value={String(basics.max_teams)}
                      onValueChange={(value) => setBasics((prev) => ({ ...prev, max_teams: Number(value) }))}
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
                        className="data-[state=checked]:bg-[#22C55E] data-[state=unchecked]:bg-[#334155] focus-visible:ring-[#22C55E]/30"
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
                  description="Review roster structure and scoring settings that will be persisted with this league."
                />

                <div className="space-y-4">
                  <Label className={fieldLabelClass}>Fixed roster format</Label>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
                    {Object.entries(rosterSlots).map(([slot, value]) => (
                      <div key={slot} className="rounded-[12px] border border-white/[0.08] bg-[#161E2E] p-4">
                        <span className="text-xs font-semibold text-[#94A3B8]">{slot}</span>
                        <p className="mt-2 text-2xl font-bold text-[#22C55E]">{value}</p>
                      </div>
                    ))}
                  </div>
                  <p className="text-sm leading-6 text-[#94A3B8]">
                    Locked for all leagues: QB, RB, RB, WR, WR, TE, K + 4 Bench + 1 IR. No defensive players.
                  </p>
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
                        {playoffOptions.map((option) => (
                          <SelectItem key={option} value={String(option)} className="text-sm font-medium">
                            {option} Teams
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="Waiver type">
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

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                  <Field label="PPR">
                    <Input
                      type="number"
                      step="0.5"
                      value={scoring.ppr}
                      onChange={(e) => setScoring((prev) => ({ ...prev, ppr: Number(e.target.value) }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Pass TD">
                    <Input
                      type="number"
                      value={scoring.pass_td}
                      onChange={(e) => setScoring((prev) => ({ ...prev, pass_td: Number(e.target.value) }))}
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Interception">
                    <Input
                      type="number"
                      value={scoring.int}
                      onChange={(e) => setScoring((prev) => ({ ...prev, int: Number(e.target.value) }))}
                      className={inputClass}
                    />
                  </Field>
                </div>

                <div className="flex flex-col gap-2 rounded-[14px] border border-white/[0.08] bg-[#161E2E] p-4 sm:flex-row sm:items-center sm:justify-between">
                  <span className={fieldLabelClass}>Format flags</span>
                  <span className="text-sm font-semibold text-[#22C55E]">
                    Superflex Off · Kicker On · Defense Off
                  </span>
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
                    <Input
                      value={draft.timezone}
                      onChange={(e) => setDraft((prev) => ({ ...prev, timezone: e.target.value }))}
                      className={inputClass}
                    />
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
                      <Calendar className="h-4 w-4 text-[#22C55E]" />
                      Draft starts in {draftCountdown || "--"}
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
                  <ReviewItem label="Draft" value={draftDateTime?.toLocaleString() || "--"} />
                  <ReviewItem label="Commissioner" value="You" />
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
    </div>
  );
}
