import React, { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Calendar, Check, ChevronLeft, ChevronRight, Copy, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  const date = draft.toISOString().slice(0, 10);
  return date;
};

const getDefaultDraftTime = () => "19:00";

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
    const local = new Date(`${draft.draft_date}T${draft.draft_time}:00`);
    return local;
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
      const response = await apiPost<LeagueCreateResponse>("/leagues/create", payload);
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
    <div className="max-w-5xl mx-auto py-12 space-y-8" data-create-step={step}>
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
              <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                Fixed Roster Format
              </Label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(rosterSlots).map(([slot, value]) => (
                <div key={slot} className="h-11 rounded-xl bg-white/5 border border-border px-4 flex items-center justify-between">
                  <span className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/70">{slot}</span>
                  <span className="text-sm font-black text-primary">{value}</span>
                </div>
              ))}
              </div>
              <p className="text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground/55">
                Locked for all leagues: QB, RB, RB, WR, WR, TE, K + 4 Bench + 1 IR. No defensive players.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Playoff Teams</Label>
                <Select
                  value={String(settings.playoff_teams)}
                  onValueChange={(value) => setSettings((prev) => ({ ...prev, playoff_teams: Number(value) }))}
                >
                  <SelectTrigger className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    {playoffOptions.map((option) => (
                      <SelectItem key={option} value={String(option)} className="text-sm font-bold">
                        {option} Teams
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Waiver Type</Label>
                <Select
                  value={settings.waiver_type}
                  onValueChange={(value) => setSettings((prev) => ({ ...prev, waiver_type: value }))}
                >
                  <SelectTrigger className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    {waiverOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value} className="text-sm font-bold">
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Trade Review</Label>
                <Select
                  value={settings.trade_review_type}
                  onValueChange={(value) => setSettings((prev) => ({ ...prev, trade_review_type: value }))}
                >
                  <SelectTrigger className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-xl">
                    {tradeReviewOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value} className="text-sm font-bold">
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">PPR</Label>
                <Input
                  type="number"
                  step="0.5"
                  value={scoring.ppr}
                  onChange={(e) => setScoring((prev) => ({ ...prev, ppr: Number(e.target.value) }))}
                  className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Pass TD</Label>
                <Input
                  type="number"
                  value={scoring.pass_td}
                  onChange={(e) => setScoring((prev) => ({ ...prev, pass_td: Number(e.target.value) }))}
                  className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">INT</Label>
                <Input
                  type="number"
                  value={scoring.int}
                  onChange={(e) => setScoring((prev) => ({ ...prev, int: Number(e.target.value) }))}
                  className="h-11 rounded-xl bg-white/5 border-border text-sm font-bold"
                />
              </div>
            </div>

            <div className="h-11 rounded-xl bg-white/5 border border-border px-4 flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/70">
                Format Flags
              </span>
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                Superflex Off • Kicker On • Defense Off
              </span>
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

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
                <p className="text-[10px] text-muted-foreground/60">Commissioner</p>
                <p className="text-primary">You</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
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
            className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
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
  );
}
