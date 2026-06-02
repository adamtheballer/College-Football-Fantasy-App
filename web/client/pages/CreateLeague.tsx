import React, { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Info,
  Loader2,
  Lock,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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
const SETTINGS_PRESET_KEYS = ["casual", "competitive", "high_scoring", "custom"] as const;
type SettingsPreset = (typeof SETTINGS_PRESET_KEYS)[number];

const SETTINGS_PRESETS: Record<
  Exclude<SettingsPreset, "custom">,
  {
    label: string;
    scoring: { ppr: number; pass_td: number; int: number };
    waiver_type: string;
    trade_review_type: string;
  }
> = {
  casual: {
    label: "Casual",
    scoring: { ppr: 1, pass_td: 4, int: -2 },
    waiver_type: "rolling",
    trade_review_type: "none",
  },
  competitive: {
    label: "Competitive",
    scoring: { ppr: 1, pass_td: 4, int: -2 },
    waiver_type: "faab",
    trade_review_type: "commissioner",
  },
  high_scoring: {
    label: "High Scoring",
    scoring: { ppr: 1.5, pass_td: 6, int: -1 },
    waiver_type: "faab",
    trade_review_type: "league_vote",
  },
};

const getDefaultDraftDate = () => {
  const now = new Date();
  const draft = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  const date = draft.toISOString().slice(0, 10);
  return date;
};

const getDefaultDraftTime = () => "19:00";

const labelClassName = "text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground/80";

function SettingLabel({
  htmlFor,
  label,
  description,
}: {
  htmlFor?: string;
  label: string;
  description: string;
}) {
  return (
    <Label htmlFor={htmlFor} className={labelClassName}>
      <span className="inline-flex items-center gap-2">
        {label}
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={`${label} help`}
              className="rounded-full p-0.5 text-muted-foreground/60 transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
            >
              <Info className="h-3.5 w-3.5" />
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-[220px] border-white/15 bg-[#0b1220] text-[11px] leading-5 text-foreground">
            {description}
          </TooltipContent>
        </Tooltip>
      </span>
    </Label>
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
  const [settingsPreset, setSettingsPreset] = useState<SettingsPreset>("competitive");

  const [draft, setDraft] = useState({
    draft_date: getDefaultDraftDate(),
    draft_time: getDefaultDraftTime(),
    timezone,
    draft_type: "snake",
    pick_timer_seconds: 90,
    order_strategy: "fixed",
  });

  const draftDateTime = useMemo(() => {
    if (!draft.draft_date || !draft.draft_time) return null;
    const local = new Date(`${draft.draft_date}T${draft.draft_time}:00`);
    return local;
  }, [draft.draft_date, draft.draft_time]);

  const draftCountdown = useMemo(() => {
    if (!draftDateTime) return null;
    const diffMs = draftDateTime.getTime() - Date.now();
    const days = Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
    return `${days} days`;
  }, [draftDateTime]);

  const settingsErrors = useMemo(() => {
    const errors: Partial<Record<"playoff_teams" | "ppr" | "pass_td" | "int", string>> = {};
    if (Number.isNaN(scoring.ppr) || scoring.ppr < 0 || scoring.ppr > 2) {
      errors.ppr = "PPR must be between 0 and 2.";
    }
    if (Number.isNaN(scoring.pass_td) || scoring.pass_td < 4 || scoring.pass_td > 6) {
      errors.pass_td = "Pass TD must be between 4 and 6.";
    }
    if (Number.isNaN(scoring.int) || scoring.int < -6 || scoring.int > 0) {
      errors.int = "INT must be between -6 and 0.";
    }
    if (settings.playoff_teams > basics.max_teams) {
      errors.playoff_teams = `Playoff teams cannot exceed league size (${basics.max_teams}).`;
    }
    return errors;
  }, [basics.max_teams, scoring.int, scoring.pass_td, scoring.ppr, settings.playoff_teams]);

  const settingsValid = Object.keys(settingsErrors).length === 0;

  const settingsSummary = useMemo(() => {
    const pprLabel =
      scoring.ppr === 1
        ? "Full PPR"
        : scoring.ppr === 0.5
          ? "Half PPR"
          : scoring.ppr === 0
            ? "Standard"
            : `${scoring.ppr} PPR`;
    const waiverLabel = waiverOptions.find((option) => option.value === settings.waiver_type)?.label ?? "Waivers";
    return `Superflex Off • Kicker On • Defense Off • ${pprLabel} • ${waiverLabel}`;
  }, [scoring.ppr, settings.waiver_type]);

  const canContinue = useMemo(() => {
    if (step === 0) {
      return basics.name.trim().length > 2 && basics.max_teams > 0;
    }
    if (step === 1) {
      return settingsValid;
    }
    if (step === 2) {
      return !!draft.draft_date && !!draft.draft_time;
    }
    return true;
  }, [basics.name, basics.max_teams, draft.draft_date, draft.draft_time, settingsValid, step]);

  const applySettingsPreset = (preset: SettingsPreset) => {
    setSettingsPreset(preset);
    if (preset === "custom") return;
    const selected = SETTINGS_PRESETS[preset];
    setScoring((prev) => ({
      ...prev,
      ppr: selected.scoring.ppr,
      pass_td: selected.scoring.pass_td,
      int: selected.scoring.int,
    }));
    setSettings((prev) => ({
      ...prev,
      waiver_type: selected.waiver_type,
      trade_review_type: selected.trade_review_type,
    }));
  };

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
          order_strategy: draft.order_strategy,
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
      <div className="max-w-3xl mx-auto py-20 space-y-6">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem] p-12 text-center space-y-6">
          <h1 className="text-4xl font-black italic uppercase text-foreground">Sign In Required</h1>
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-widest">
            Please sign in to create a league.
          </p>
          <Button type="button" onClick={() => navigate("/login")} className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black tracking-[0.2em] uppercase">
            Go to Login
          </Button>
        </Card>
      </div>
    );
  }

  if (success) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-8">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem] p-12 space-y-8">
          <div className="space-y-3">
            <h1 className="text-5xl font-black italic uppercase text-foreground">League Created</h1>
            <p className="text-sm font-medium text-muted-foreground uppercase tracking-[0.2em]">
              Invite your league and get ready to draft.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6 space-y-3">
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Invite Code</p>
              <div className="flex items-center justify-between gap-4">
                <span className="text-xl font-black tracking-[0.2em] text-primary">{success.invite_code}</span>
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 px-4 rounded-xl text-[10px] font-black uppercase tracking-widest"
                  onClick={() => navigator.clipboard.writeText(success.invite_code)}
                >
                  <Copy className="w-4 h-4 mr-2" />
                  Copy
                </Button>
              </div>
            </Card>

            <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6 space-y-3">
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Invite Link</p>
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs font-bold text-muted-foreground truncate">{success.invite_link}</span>
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 px-4 rounded-xl text-[10px] font-black uppercase tracking-widest"
                  onClick={() => navigator.clipboard.writeText(success.invite_link)}
                >
                  <Copy className="w-4 h-4 mr-2" />
                  Copy
                </Button>
              </div>
            </Card>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Button
              type="button"
              className="h-12 px-6 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate(`/league/${success.league.id}`)}
            >
              Go to League Home
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-12 px-6 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate("/leagues")}
            >
              Back to Leagues
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto py-12 pb-28 md:pb-12 space-y-8" data-create-step={step}>
      <div className="space-y-4">
        <h1 className="text-6xl font-black italic uppercase text-foreground">Create League</h1>
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-[0.2em]">
          Step {step + 1} of {steps.length} • {steps[step]}
        </p>
      </div>

      <div className="flex items-center gap-2">
        {steps.map((label, idx) => (
          <div key={label} className="flex-1">
            <div className={cn("h-1 rounded-full", idx <= step ? "bg-primary" : "bg-white/10")} />
            <p className={cn("mt-2 text-[9px] font-black uppercase tracking-[0.3em]", idx <= step ? "text-primary" : "text-muted-foreground/40")}>
              {label}
            </p>
          </div>
        ))}
      </div>

      {error && (
        <div className="text-sm font-bold text-red-400 uppercase tracking-[0.2em]">{error}</div>
      )}

      {step === 0 && (
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardHeader className="px-10 pt-10">
            <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">League Basics</CardTitle>
          </CardHeader>
          <CardContent className="px-10 pb-10 space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label className="text-[10px] font-black tracking-[0.3em] uppercase text-muted-foreground/70">League Name</Label>
                <Input
                  value={basics.name}
                  onChange={(e) => setBasics((prev) => ({ ...prev, name: e.target.value }))}
                  className="h-12 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black tracking-[0.3em] uppercase text-muted-foreground/70">Season Year</Label>
                <Input
                  type="number"
                  value={basics.season_year}
                  onChange={(e) => setBasics((prev) => ({ ...prev, season_year: Number(e.target.value) }))}
                  className="h-12 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label className="text-[10px] font-black tracking-[0.3em] uppercase text-muted-foreground/70">League Size</Label>
                <Select
                  value={String(basics.max_teams)}
                  onValueChange={(value) => setBasics((prev) => ({ ...prev, max_teams: Number(value) }))}
                >
                  <SelectTrigger className="h-12 rounded-xl bg-white/5 border-border text-sm font-bold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    {leagueSizes.map((size) => (
                      <SelectItem key={size} value={String(size)} className="text-sm font-bold">
                        {size} Teams
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black tracking-[0.3em] uppercase text-muted-foreground/70">Private League</Label>
                <div className="flex items-center gap-3 h-12 px-4 rounded-xl bg-white/5 border border-border">
                  <Switch
                    checked={basics.is_private}
                    onCheckedChange={(value) => setBasics((prev) => ({ ...prev, is_private: value }))}
                  />
                  <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                    {basics.is_private ? "Invite Only" : "Public"}
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-[10px] font-black tracking-[0.3em] uppercase text-muted-foreground/70">Description (Optional)</Label>
              <Input
                value={basics.description}
                onChange={(e) => setBasics((prev) => ({ ...prev, description: e.target.value }))}
                className="h-12 rounded-xl bg-white/5 border-border text-sm font-bold"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[10px] font-black tracking-[0.3em] uppercase text-muted-foreground/70">League Image URL (Optional)</Label>
              <Input
                value={basics.icon_url}
                onChange={(e) => setBasics((prev) => ({ ...prev, icon_url: e.target.value }))}
                className="h-12 rounded-xl bg-white/5 border-border text-sm font-bold"
              />
            </div>
          </CardContent>
        </Card>
      )}

      {step === 1 && (
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardHeader className="px-10 pt-10">
            <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">League Settings</CardTitle>
          </CardHeader>
          <CardContent className="px-10 pb-10 space-y-8">
            <div className="space-y-3">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground/80">
                Presets
              </p>
              <div className="flex flex-wrap gap-3">
                {SETTINGS_PRESET_KEYS.map((presetKey) => {
                  const selected = settingsPreset === presetKey;
                  const label =
                    presetKey === "custom"
                      ? "Custom"
                      : SETTINGS_PRESETS[presetKey as Exclude<SettingsPreset, "custom">].label;
                  return (
                    <button
                      key={presetKey}
                      type="button"
                      onClick={() => applySettingsPreset(presetKey)}
                      className={cn(
                        "h-10 rounded-xl border px-4 text-[10px] font-black uppercase tracking-[0.18em] transition-colors",
                        selected
                          ? "border-primary/50 bg-primary/15 text-primary"
                          : "border-white/10 bg-white/[0.03] text-muted-foreground hover:border-white/20 hover:text-foreground"
                      )}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-amber-300/35 bg-amber-400/10 px-3 py-1">
                  <Lock className="h-3.5 w-3.5 text-amber-200" />
                  <span className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-100">
                    Locked Format
                  </span>
                </div>
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground/80">
                  Fixed Roster Format
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
                {Object.entries(rosterSlots).map(([slot, value]) => (
                  <div
                    key={slot}
                    className="h-12 rounded-xl border border-white/10 bg-black/20 px-3 flex items-center justify-between"
                  >
                    <span className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground/80">
                      {slot}
                    </span>
                    <span className="text-sm font-black text-primary">{value}</span>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground/75">
                Roster format is locked for competitive balance.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
              <div className="space-y-2">
                <SettingLabel
                  label="Playoff Teams"
                  description="Number of teams that qualify for playoffs. Keep this proportional to league size."
                />
                <Select
                  value={String(settings.playoff_teams)}
                  onValueChange={(value) =>
                    setSettings((prev) => ({ ...prev, playoff_teams: Number(value) }))
                  }
                >
                  <SelectTrigger className="h-11 cfb-control text-sm font-semibold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    {playoffOptions.map((option) => (
                      <SelectItem key={option} value={String(option)} className="text-sm font-semibold">
                        {option} Teams
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {settingsErrors.playoff_teams && (
                  <p className="text-[11px] font-semibold text-red-300">{settingsErrors.playoff_teams}</p>
                )}
              </div>
              <div className="space-y-2">
                <SettingLabel
                  label="Waiver Type"
                  description="FAAB uses bidding dollars, rolling keeps waiver order, reverse standings gives priority to lower-ranked teams."
                />
                <Select
                  value={settings.waiver_type}
                  onValueChange={(value) => {
                    setSettingsPreset("custom");
                    setSettings((prev) => ({ ...prev, waiver_type: value }));
                  }}
                >
                  <SelectTrigger className="h-11 cfb-control text-sm font-semibold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    {waiverOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value} className="text-sm font-semibold">
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <SettingLabel
                  label="Trade Review"
                  description="Choose whether trades require commissioner approval, league votes, or process instantly."
                />
                <Select
                  value={settings.trade_review_type}
                  onValueChange={(value) => {
                    setSettingsPreset("custom");
                    setSettings((prev) => ({ ...prev, trade_review_type: value }));
                  }}
                >
                  <SelectTrigger className="h-11 cfb-control text-sm font-semibold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    {tradeReviewOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value} className="text-sm font-semibold">
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <SettingLabel
                  label="PPR"
                  description="Points per reception. 0 = standard, 0.5 = half-PPR, 1 = full PPR."
                />
                <Input
                  type="number"
                  step="0.5"
                  min={0}
                  max={2}
                  value={scoring.ppr}
                  onChange={(e) => {
                    setSettingsPreset("custom");
                    setScoring((prev) => ({ ...prev, ppr: Number(e.target.value) }));
                  }}
                  className="h-11 cfb-control text-sm font-semibold"
                />
                {settingsErrors.ppr && (
                  <p className="text-[11px] font-semibold text-red-300">{settingsErrors.ppr}</p>
                )}
              </div>
              <div className="space-y-2">
                <SettingLabel
                  label="Pass TD"
                  description="Fantasy points awarded per passing touchdown."
                />
                <Input
                  type="number"
                  min={4}
                  max={6}
                  value={scoring.pass_td}
                  onChange={(e) => {
                    setSettingsPreset("custom");
                    setScoring((prev) => ({ ...prev, pass_td: Number(e.target.value) }));
                  }}
                  className="h-11 cfb-control text-sm font-semibold"
                />
                {settingsErrors.pass_td && (
                  <p className="text-[11px] font-semibold text-red-300">{settingsErrors.pass_td}</p>
                )}
              </div>
              <div className="space-y-2">
                <SettingLabel
                  label="INT"
                  description="Fantasy points lost when a QB throws an interception."
                />
                <Input
                  type="number"
                  min={-6}
                  max={0}
                  value={scoring.int}
                  onChange={(e) => {
                    setSettingsPreset("custom");
                    setScoring((prev) => ({ ...prev, int: Number(e.target.value) }));
                  }}
                  className="h-11 cfb-control text-sm font-semibold"
                />
                {settingsErrors.int && (
                  <p className="text-[11px] font-semibold text-red-300">{settingsErrors.int}</p>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 space-y-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground/80">
                League Format Summary
              </p>
              <p className="text-sm font-semibold text-primary">{settingsSummary}</p>
              <div className="grid grid-cols-1 gap-2 text-[11px] text-muted-foreground/75 md:grid-cols-2">
                <p>Superflex: Off</p>
                <p>Kicker: On</p>
                <p>Defense: Off</p>
                <p>Trade Review: {tradeReviewOptions.find((option) => option.value === settings.trade_review_type)?.label ?? settings.trade_review_type}</p>
              </div>
            </div>

            {!settingsValid && (
              <div className="rounded-xl border border-red-400/30 bg-red-500/10 p-4">
                <p className="text-[11px] font-semibold text-red-200">
                  Fix settings errors before continuing.
                </p>
              </div>
            )}

            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 text-[11px] text-muted-foreground/80 space-y-1">
              <p className="font-semibold uppercase tracking-[0.14em]">Format Toggles</p>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div className="space-y-1">
                  <SettingLabel
                    label="Superflex"
                    description="When enabled, an extra starter slot can use a QB, RB, WR, or TE. Locked off in this format."
                  />
                  <p className="text-sm font-semibold text-foreground">Off (Locked)</p>
                </div>
                <div className="space-y-1">
                  <SettingLabel
                    label="Kicker"
                    description="Includes kicker scoring in league totals. Locked on in this format."
                  />
                  <p className="text-sm font-semibold text-foreground">On (Locked)</p>
                </div>
                <div className="space-y-1">
                  <SettingLabel
                    label="Defense"
                    description="Includes team-defense roster spots and defensive scoring. Locked off in this format."
                  />
                  <p className="text-sm font-semibold text-foreground">Off (Locked)</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardHeader className="px-10 pt-10">
            <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Draft Schedule</CardTitle>
          </CardHeader>
          <CardContent className="px-10 pb-10 space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Draft Date</Label>
                <Input
                  type="date"
                  value={draft.draft_date}
                  onChange={(e) => setDraft((prev) => ({ ...prev, draft_date: e.target.value }))}
                  className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Draft Time</Label>
                <Input
                  type="time"
                  value={draft.draft_time}
                  onChange={(e) => setDraft((prev) => ({ ...prev, draft_time: e.target.value }))}
                  className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Time Zone</Label>
                <Input
                  value={draft.timezone}
                  onChange={(e) => setDraft((prev) => ({ ...prev, timezone: e.target.value }))}
                  className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Draft Type</Label>
                <Select
                  value={draft.draft_type}
                  onValueChange={(value) => setDraft((prev) => ({ ...prev, draft_type: value }))}
                >
                  <SelectTrigger className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    <SelectItem value="snake" className="text-sm font-bold">Snake Draft</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Draft Order</Label>
                <Select
                  value={draft.order_strategy}
                  onValueChange={(value) => setDraft((prev) => ({ ...prev, order_strategy: value }))}
                >
                  <SelectTrigger className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    <SelectItem value="fixed" className="text-sm font-bold">Set Order</SelectItem>
                    <SelectItem value="random" className="text-sm font-bold">Random Order</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Pick Timer (sec)</Label>
                <Input
                  type="number"
                  value={draft.pick_timer_seconds}
                  onChange={(e) => setDraft((prev) => ({ ...prev, pick_timer_seconds: Number(e.target.value) }))}
                  className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Preview</Label>
                <div className="h-11 rounded-xl bg-white/5 border border-border flex items-center gap-3 px-4 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                  <Calendar className="w-4 h-4 text-primary" />
                  Draft starts in {draftCountdown || "--"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 3 && (
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardHeader className="px-10 pt-10">
            <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Review</CardTitle>
          </CardHeader>
          <CardContent className="px-10 pb-10 space-y-6 text-sm font-bold uppercase tracking-widest text-muted-foreground">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-[10px] text-muted-foreground/60">League Name</p>
                <p className="text-primary">{basics.name}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground/60">Teams</p>
                <p className="text-primary">{basics.max_teams}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground/60">Draft</p>
                <p className="text-primary">{draftDateTime?.toLocaleString() || "--"}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground/60">Draft Order</p>
                <p className="text-primary">{draft.order_strategy === "random" ? "Random" : "Set Order"}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground/60">Commissioner</p>
                <p className="text-primary">You</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="fixed bottom-3 left-3 right-3 z-30 rounded-2xl border border-white/10 bg-[#071024]/95 p-3 backdrop-blur-md md:static md:rounded-none md:border-0 md:bg-transparent md:p-0">
        <div className="flex items-center justify-between gap-3">
          <Button
            type="button"
            variant="outline"
            className="h-12 px-6 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
            onClick={step === 0 ? () => navigate("/leagues") : handleBack}
          >
            <ChevronLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          {step < steps.length - 1 ? (
            <Button
              type="button"
              className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em] disabled:opacity-45 disabled:cursor-not-allowed"
              disabled={!canContinue}
              onClick={handleNext}
            >
              Continue
              <ChevronRight className="w-4 h-4 ml-2" />
            </Button>
          ) : (
            <Button
              type="button"
              className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={handleCreate}
              disabled={loading}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
              Create League
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
