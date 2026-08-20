import { Bell, Check, Info, LoaderCircle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/hooks/use-auth";
import { apiGet, apiPost } from "@/lib/api";
import { enableBrowserPush, getBrowserPushState, prepareBrowserPush, type BrowserPushState } from "@/lib/push-notifications";

type Preferences = {
  push_enabled: boolean;
  email_enabled: boolean;
  draft_alerts: boolean;
  injury_alerts: boolean;
  usage_alerts: boolean;
  waiver_alerts: boolean;
  projection_alerts: boolean;
  lineup_reminders: boolean;
  trade_alerts: boolean;
  chat_alerts: boolean;
  matchup_results: boolean;
  matchup_start_alerts: boolean;
  matchup_result_alerts: boolean;
  big_play_alerts: boolean;
  long_rush_alerts: boolean;
  long_reception_alerts: boolean;
  long_pass_alerts: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  timezone: string;
};

type PreferenceToggleKey =
  | "draft_alerts"
  | "injury_alerts"
  | "usage_alerts"
  | "waiver_alerts"
  | "projection_alerts"
  | "lineup_reminders"
  | "trade_alerts"
  | "chat_alerts"
  | "matchup_start_alerts"
  | "matchup_result_alerts"
  | "big_play_alerts"
  | "long_rush_alerts"
  | "long_reception_alerts"
  | "long_pass_alerts";

type LeaguePreference = {
  league_id: number;
  league_name: string | null;
  enabled: boolean;
  injury_alerts: boolean;
  big_play_alerts: boolean;
  projection_alerts: boolean;
  draft_alerts: boolean;
  trade_alerts: boolean;
  waiver_alerts: boolean;
  matchup_start_alerts: boolean;
  matchup_result_alerts: boolean;
  lineup_reminders: boolean;
  long_rush_alerts: boolean;
  long_reception_alerts: boolean;
  long_pass_alerts: boolean;
};

type LeaguePreferencesResponse = { data: LeaguePreference[] };

const rows: Array<{ key: PreferenceToggleKey; label: string; description: string }> = [
  { key: "draft_alerts", label: "Drafts", description: "Draft reminders, your turn, and completion." },
  { key: "trade_alerts", label: "Trades", description: "Offers and important trade decisions." },
  { key: "waiver_alerts", label: "Waivers", description: "Claim results and status changes." },
  { key: "matchup_start_alerts", label: "Matchup starts", description: "Your lineup's first verified kickoff." },
  { key: "matchup_result_alerts", label: "Matchup results", description: "Only after scoring certifies the result." },
  { key: "lineup_reminders", label: "Lineup reminders", description: "A reminder before your first verified starter kickoff." },
  { key: "chat_alerts", label: "Chat", description: "Private direct-message alerts." },
];

const longPlayRows: Array<{ key: "long_rush_alerts" | "long_reception_alerts" | "long_pass_alerts"; label: string; description: string }> = [
  { key: "long_rush_alerts", label: "Long rushes", description: "30+ yard rushing plays." },
  { key: "long_reception_alerts", label: "Long receptions", description: "40+ yard receptions." },
  { key: "long_pass_alerts", label: "Long passes", description: "40+ yard completed passes." },
];

type LeagueToggleKey = "draft_alerts" | "trade_alerts" | "waiver_alerts" | "matchup_start_alerts" | "matchup_result_alerts" | "lineup_reminders" | "big_play_alerts" | "long_rush_alerts" | "long_reception_alerts" | "long_pass_alerts";

const leagueRows: Array<{ key: LeagueToggleKey; label: string }> = [
  { key: "draft_alerts", label: "Drafts" },
  { key: "trade_alerts", label: "Trades" },
  { key: "waiver_alerts", label: "Waivers" },
  { key: "matchup_start_alerts", label: "Starts" },
  { key: "matchup_result_alerts", label: "Results" },
  { key: "lineup_reminders", label: "Lineup" },
  { key: "big_play_alerts", label: "Big plays" },
  { key: "long_rush_alerts", label: "Long rushes" },
  { key: "long_reception_alerts", label: "Long receptions" },
  { key: "long_pass_alerts", label: "Long passes" },
];

const permissionCopy: Record<BrowserPushState, string> = {
  default: "Get alerts for drafts, trades, waivers, and important fantasy updates.",
  granted: "Push notifications are enabled for this browser.",
  denied: "Browser notifications are blocked. Update this site's permission in your browser settings to enable them.",
  unsupported: "This browser cannot receive web push here. On iPhone, add CFB Fantasy to your Home Screen first.",
  unconfigured: "Push notifications are not configured for this environment yet.",
};

export function NotificationSettingsPanel() {
  const { user } = useAuth();
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [leaguePreferences, setLeaguePreferences] = useState<LeaguePreference[] | null>(null);
  const [permission, setPermission] = useState<BrowserPushState>(getBrowserPushState());
  const [saving, setSaving] = useState(false);
  const [preparingPush, setPreparingPush] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pushAttempted, setPushAttempted] = useState(false);
  const mountedRef = useRef(false);
  const requestGenerationRef = useRef(0);
  const requestControllersRef = useRef(new Set<AbortController>());

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestGenerationRef.current += 1;
      for (const controller of requestControllersRef.current) controller.abort();
      requestControllersRef.current.clear();
    };
  }, []);

  const beginRequest = () => {
    const controller = new AbortController();
    requestControllersRef.current.add(controller);
    return { controller, generation: requestGenerationRef.current };
  };

  const finishRequest = (controller: AbortController) => {
    requestControllersRef.current.delete(controller);
  };

  const isCurrentRequest = (controller: AbortController, generation: number) =>
    mountedRef.current && !controller.signal.aborted && requestGenerationRef.current === generation;

  const isAbortError = (error: unknown) => error instanceof DOMException && error.name === "AbortError";

  const pushDeliveryEnabled = permission === "granted" && preferences?.push_enabled === true;
  const pushStatus = saving
    ? { label: "Checking permission…", icon: LoaderCircle, className: "text-sky-300" }
    : preparingPush
      ? { label: "Preparing notification request…", icon: LoaderCircle, className: "text-sky-300" }
    : pushDeliveryEnabled
      ? { label: "Enabled", icon: Check, className: "text-emerald-300" }
      : permission === "granted"
        ? { label: "Permission granted — enable delivery below", icon: Info, className: "text-amber-300" }
        : permission === "denied"
          ? { label: "Blocked", icon: X, className: "text-rose-300" }
          : permission === "unsupported"
            ? { label: "Add to Home Screen", icon: X, className: "text-amber-300" }
            : permission === "unconfigured"
              ? { label: "Unavailable", icon: X, className: "text-rose-300" }
              : { label: pushAttempted ? "Permission not granted" : "Not enabled", icon: X, className: "text-muted-foreground" };
  const PushStatusIcon = pushStatus.icon;

  useEffect(() => {
    // A user transition invalidates non-abortable SDK work started for the
    // prior identity as well as this effect's abortable API requests.
    requestGenerationRef.current += 1;
    const { controller, generation } = beginRequest();
    if (!user) {
      if (isCurrentRequest(controller, generation)) {
        setPreferences(null);
        setLeaguePreferences(null);
      }
      finishRequest(controller);
      return () => controller.abort();
    }
    Promise.all([
      apiGet<Preferences>("/notifications/preferences", undefined, controller.signal),
      apiGet<LeaguePreferencesResponse>("/notifications/league-preferences", undefined, controller.signal),
    ])
      .then(([nextPreferences, leagueResponse]) => {
        if (!isCurrentRequest(controller, generation)) return;
        setPreferences(nextPreferences);
        setLeaguePreferences(leagueResponse.data);
      })
      .catch((error: unknown) => {
        if (!isCurrentRequest(controller, generation) || isAbortError(error)) return;
        setMessage("Unable to load notification settings.");
      })
      .finally(() => finishRequest(controller));
    return () => controller.abort();
  }, [user?.id]);

  useEffect(() => {
    if (!user || permission === "denied" || permission === "unsupported" || permission === "unconfigured") return;
    let active = true;
    setPreparingPush(true);
    void prepareBrowserPush(user.id)
      .catch((error: unknown) => {
        if (active) setMessage(error instanceof Error ? error.message : "Unable to prepare push notifications.");
      })
      .finally(() => {
        if (active) setPreparingPush(false);
      });
    return () => {
      active = false;
    };
  }, [permission, user?.id]);

  const save = async (next: Preferences) => {
    const { controller, generation } = beginRequest();
    setPreferences(next);
    setSaving(true);
    setMessage(null);
    try {
      const saved = await apiPost<Preferences>("/notifications/preferences", next, undefined, controller.signal);
      if (isCurrentRequest(controller, generation)) setPreferences(saved);
    } catch (error) {
      if (!isCurrentRequest(controller, generation) || isAbortError(error)) return;
      setMessage("Unable to save notification settings.");
    } finally {
      finishRequest(controller);
      if (isCurrentRequest(controller, generation)) setSaving(false);
    }
  };

  const enablePush = async () => {
    if (!user) return;
    const { controller, generation } = beginRequest();
    setSaving(true);
    setMessage(null);
    setPushAttempted(true);
    try {
      const nextPermission = await enableBrowserPush(user.id);
      if (!isCurrentRequest(controller, generation)) return;
      setPermission(nextPermission);
      if (nextPermission === "granted" && preferences) {
        await save({ ...preferences, push_enabled: true });
      } else if (nextPermission === "default") {
        setMessage("iPhone did not grant notification permission. Open CFB Fantasy from its Home Screen icon and try again.");
      }
    } catch (error) {
      if (!isCurrentRequest(controller, generation) || isAbortError(error)) return;
      setMessage(error instanceof Error ? error.message : "Unable to enable push notifications.");
    } finally {
      finishRequest(controller);
      if (isCurrentRequest(controller, generation)) setSaving(false);
    }
  };

  const saveLeaguePreference = async (nextLeague: LeaguePreference) => {
    if (!leaguePreferences) return;
    const { controller, generation } = beginRequest();
    const next = leaguePreferences.map((item) => item.league_id === nextLeague.league_id ? nextLeague : item);
    setLeaguePreferences(next);
    setSaving(true);
    setMessage(null);
    try {
      const response = await apiPost<LeaguePreferencesResponse>("/notifications/league-preferences", { items: next }, undefined, controller.signal);
      if (isCurrentRequest(controller, generation)) setLeaguePreferences(response.data);
    } catch (error) {
      if (!isCurrentRequest(controller, generation) || isAbortError(error)) return;
      setMessage("Unable to save league notification settings.");
    } finally {
      finishRequest(controller);
      if (isCurrentRequest(controller, generation)) setSaving(false);
    }
  };

  return (
    <Card className="rounded-lg border-border bg-card shadow-none">
      <CardHeader className="border-b border-border px-4 py-4 sm:px-5">
        <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.16em] text-foreground">
          <Bell className="h-4 w-4 text-primary" /> Notifications
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 p-4 sm:p-5">
        <div className="mb-3 flex flex-col gap-3 rounded-md border border-border bg-muted/20 p-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-bold text-foreground">Push notifications</p>
            <p className="text-xs leading-relaxed text-muted-foreground">{permissionCopy[permission]}</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            {permission !== "granted" ? (
              <Button onClick={() => void enablePush()} disabled={saving || preparingPush || permission === "denied" || permission === "unsupported" || permission === "unconfigured"} className="h-9 rounded-md text-[10px] font-black uppercase tracking-[0.12em] shadow-none">
                {saving ? "Checking permission…" : preparingPush ? "Preparing notifications…" : "Enable push notifications"}
              </Button>
            ) : null}
            <span data-testid="push-status" aria-live="polite" className={`inline-flex items-center gap-1 text-xs font-bold ${pushStatus.className}`}>
              <PushStatusIcon className={`h-4 w-4 ${saving || preparingPush ? "animate-spin" : ""}`} /> {pushStatus.label}
            </span>
          </div>
        </div>
        {preferences ? rows.map((row) => (
          <div key={row.key} className="flex items-center justify-between gap-5 border-b border-border/35 py-3 last:border-0">
            <div><p className="text-sm font-bold text-foreground">{row.label}</p><p className="text-xs text-muted-foreground">{row.description}</p></div>
            <Switch checked={Boolean(preferences[row.key])} disabled={saving} onCheckedChange={(checked) => void save({ ...preferences, [row.key]: checked })} aria-label={`${row.label} notifications`} />
          </div>
        )) : <p className="text-sm text-muted-foreground">Loading notification settings…</p>}
        {preferences ? <div className="border-b border-border/35 py-4" data-testid="big-play-alert-group">
          <div className="flex items-center justify-between gap-5">
            <div><p className="text-sm font-bold text-foreground">Big Plays</p><p className="text-xs text-muted-foreground">Master control for verified live long-play alerts. Turning it off mutes every sub-alert.</p></div>
            <Switch checked={preferences.big_play_alerts} disabled={saving} onCheckedChange={(big_play_alerts) => void save({ ...preferences, big_play_alerts })} aria-label="Big Plays notifications" />
          </div>
          <div className="ml-3 mt-3 space-y-1 border-l border-primary/30 pl-4 sm:ml-5">
            {longPlayRows.map((row) => <div key={row.key} className="flex items-center justify-between gap-4 py-2">
              <div><p className="text-xs font-semibold text-foreground">{row.label}</p><p className="text-[11px] text-muted-foreground">{row.description}</p></div>
              <Switch checked={Boolean(preferences[row.key])} disabled={saving || !preferences.big_play_alerts} onCheckedChange={(checked) => void save({ ...preferences, [row.key]: checked })} aria-label={`${row.label} notifications`} />
            </div>)}
          </div>
        </div> : null}
        {preferences ? <>
          <div className="flex items-center justify-between gap-5 border-b border-border/35 py-3">
            <div><p className="text-sm font-bold text-foreground">Push delivery</p><p className="text-xs text-muted-foreground">Pause operating-system notifications without removing in-app history.</p></div>
            <Switch checked={preferences.push_enabled} disabled={saving || permission !== "granted"} onCheckedChange={(checked) => void save({ ...preferences, push_enabled: checked })} aria-label="Push delivery" />
          </div>
          <div className="flex items-center justify-between gap-5 border-b border-border/35 py-3">
            <div><p className="text-sm font-bold text-foreground">Email delivery</p><p className="text-xs text-muted-foreground">Receive enabled notification categories by email when this environment has an approved sender.</p></div>
            <Switch checked={preferences.email_enabled} disabled={saving} onCheckedChange={(checked) => void save({ ...preferences, email_enabled: checked })} aria-label="Email delivery" />
          </div>
          <div className="space-y-3 border-b border-border/35 py-4">
            <div><p className="text-sm font-bold text-foreground">Quiet hours</p><p className="text-xs text-muted-foreground">Non-urgent player updates wait until quiet hours end. Draft, trade, and waiver alerts remain time-sensitive.</p></div>
            <div className="grid grid-cols-2 gap-3 sm:max-w-sm">
              <label className="text-xs text-muted-foreground">Start<Input aria-label="Quiet hours start" type="time" value={preferences.quiet_hours_start ?? ""} onChange={(event) => setPreferences({ ...preferences, quiet_hours_start: event.target.value || null })} onBlur={(event) => void save({ ...preferences, quiet_hours_start: event.currentTarget.value || null })} /></label>
              <label className="text-xs text-muted-foreground">End<Input aria-label="Quiet hours end" type="time" value={preferences.quiet_hours_end ?? ""} onChange={(event) => setPreferences({ ...preferences, quiet_hours_end: event.target.value || null })} onBlur={(event) => void save({ ...preferences, quiet_hours_end: event.currentTarget.value || null })} /></label>
            </div>
            <label className="block max-w-sm text-xs text-muted-foreground">Timezone (IANA name)<Input aria-label="Notification timezone" value={preferences.timezone} onChange={(event) => setPreferences({ ...preferences, timezone: event.target.value })} onBlur={(event) => void save({ ...preferences, timezone: event.currentTarget.value })} placeholder="America/New_York" /></label>
            <p className="text-[11px] text-muted-foreground">Use your local timezone (currently {preferences.timezone}) for quiet hours.</p>
          </div>
          {leaguePreferences?.length ? <div className="space-y-2 border-b border-border/35 py-4">
            <div><p className="text-sm font-bold text-foreground">League notifications</p><p className="text-xs text-muted-foreground">Mute a league without changing your global preferences.</p></div>
            {leaguePreferences.map((league) => (
              <div key={league.league_id} className="space-y-3 rounded-xl border border-border/45 px-3 py-3">
                <div className="flex items-center justify-between gap-4">
                  <span className="min-w-0"><span className="block truncate text-sm font-semibold text-foreground">{league.league_name ?? `League ${league.league_id}`}</span><span className="text-[11px] text-muted-foreground">Fine-tune the categories for this league.</span></span>
                  <Switch checked={league.enabled} disabled={saving} onCheckedChange={(enabled) => void saveLeaguePreference({ ...league, enabled })} aria-label={`${league.league_name ?? "League"} notifications`} />
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3">
                  {leagueRows.map((row) => <label key={String(row.key)} className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground"><span>{row.label}</span><Switch checked={Boolean(league[row.key])} disabled={saving || !league.enabled} onCheckedChange={(checked) => void saveLeaguePreference({ ...league, [row.key]: checked })} aria-label={`${league.league_name ?? "League"} ${row.label}`} /></label>)}
                </div>
              </div>
            ))}
          </div> : null}
        </> : null}
        <p className="flex gap-2 pt-3 text-xs leading-relaxed text-muted-foreground"><Info className="mt-0.5 h-4 w-4 shrink-0" /> In-app notification history is retained even when push or email is turned off.</p>
        {message ? <p role="alert" className="text-sm text-red-300">{message}</p> : null}
      </CardContent>
    </Card>
  );
}
