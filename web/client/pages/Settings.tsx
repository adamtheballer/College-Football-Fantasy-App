import React, { useEffect, useState } from "react";
import { User, Bell, Sliders, Shield, Save, LogOut, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useNavigate } from "react-router-dom";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { restartGuide } from "@/lib/onboarding";
import { useLeagues } from "@/hooks/use-leagues";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { PasswordChangeForm } from "@/components/auth/PasswordChangeForm";

type LeagueNotificationPreference = {
  league_id: number;
  league_name: string | null;
  enabled: boolean;
  injury_alerts: boolean;
  big_play_alerts: boolean;
  projection_alerts: boolean;
};

const supportEmail = (import.meta.env.VITE_SUPPORT_EMAIL as string | undefined) || "absportscfb@gmail.com";
const privacyPolicyUrl = import.meta.env.VITE_PRIVACY_POLICY_URL as string | undefined;
const termsUrl = import.meta.env.VITE_TERMS_URL as string | undefined;
const providerDisclosureUrl = import.meta.env.VITE_PROVIDER_DISCLOSURE_URL as string | undefined;

const SettingsSection = ({ title, description, children, icon: Icon }: any) => (
  <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[2.5rem] overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.3)] group hover:border-primary/20 transition-all duration-700 relative">
    <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors" />
    <CardHeader className="px-10 pt-10 border-b border-border/40 bg-gradient-to-br from-white/5 to-transparent relative z-10">
      <div className="flex items-center gap-6">
        <div className="p-4 rounded-2xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-all duration-300 shadow-[0_0_20px_rgba(var(--primary),0.1)] group-hover:scale-110">
          <Icon className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <CardTitle className="text-[10px] font-black tracking-[0.3em] text-primary uppercase">{title}</CardTitle>
          <p className="text-[11px] font-medium text-muted-foreground/60 uppercase tracking-widest">{description}</p>
        </div>
      </div>
    </CardHeader>
    <CardContent className="p-10 space-y-8 relative z-10">
      {children}
    </CardContent>
  </Card>
);

const SettingItem = ({ label, description, children }: any) => (
  <div className="flex items-center justify-between gap-10">
    <div className="space-y-1">
      <Label className="text-sm font-black italic uppercase tracking-tight text-foreground">{label}</Label>
      {description && <p className="text-[11px] font-medium text-muted-foreground/60">{description}</p>}
    </div>
    <div className="flex-shrink-0">
      {children}
    </div>
  </div>
);

const CheckboxItem = ({ id, label, description, checked, onCheckedChange, disabled = false }: any) => (
  <div
    className={cn(
      "flex items-start space-x-4 p-4 rounded-2xl transition-colors group",
      disabled ? "opacity-50 cursor-not-allowed" : "hover:bg-white/5 cursor-pointer"
    )}
  >
    <Checkbox 
      id={id} 
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className="mt-1 border-primary/30 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
    />
    <div className="grid gap-1.5 leading-none">
      <label
        htmlFor={id}
        className="text-sm font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors cursor-pointer"
      >
        {label}
      </label>
      <p className="text-[11px] font-medium text-muted-foreground/60 uppercase tracking-widest">
        {description}
      </p>
    </div>
  </div>
);

export default function Settings() {
  const navigate = useNavigate();
  const { user, isBootstrapping, logoutAll } = useAuth();
  const { data: leagues = [] } = useLeagues(50, Boolean(user));
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [leaguePrefs, setLeaguePrefs] = useState<LeagueNotificationPreference[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [securityMessage, setSecurityMessage] = useState<string | null>(null);
  const [supportCopyState, setSupportCopyState] = useState<"idle" | "copied" | "error">("idle");
  const [prefs, setPrefs] = useState({
    push_enabled: true,
    email_enabled: true,
    draft_alerts: true,
    injury_alerts: true,
    touchdown_alerts: false,
    usage_alerts: true,
    waiver_alerts: true,
    projection_alerts: true,
    lineup_reminders: true,
  });

  useEffect(() => {
    if (!user) return;
    let active = true;
    setLoadError(null);
    apiGet<any>("/notifications/preferences")
      .then((payload) => {
        setPrefs({
          push_enabled: payload.push_enabled ?? true,
          email_enabled: payload.email_enabled ?? true,
          draft_alerts: payload.draft_alerts ?? true,
          injury_alerts: payload.injury_alerts ?? true,
          touchdown_alerts: payload.touchdown_alerts ?? false,
          usage_alerts: payload.usage_alerts ?? true,
          waiver_alerts: payload.waiver_alerts ?? true,
          projection_alerts: payload.projection_alerts ?? true,
          lineup_reminders: payload.lineup_reminders ?? true,
        });
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : "Unable to load notification preferences.");
      });
    apiGet<{ data: LeagueNotificationPreference[] }>("/notifications/league-preferences")
      .then((leaguePayload) => {
        setLeaguePrefs(leaguePayload?.data ?? []);
      })
      .catch((error) => {
        if (active) {
          setLeaguePrefs([]);
          setLoadError(error instanceof Error ? error.message : "Unable to load league notification preferences.");
        }
      });
    return () => {
      active = false;
    };
  }, [user]);

  const handleSave = async () => {
    if (!user) return;
    setSaveState("saving");
    try {
      await apiPost("/notifications/preferences", prefs);
      await apiPost("/notifications/league-preferences", {
        items: leaguePrefs.map((league) => ({
          league_id: league.league_id,
          enabled: league.enabled,
          injury_alerts: league.injury_alerts,
          big_play_alerts: league.big_play_alerts,
          projection_alerts: league.projection_alerts,
        })),
      });
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 1500);
    } catch (error) {
      setLoadError(error instanceof ApiError ? error.message : "Unable to save notification preferences.");
      setSaveState("error");
    }
  };

  const setLeaguePreference = (
    leagueId: number,
    patch: Partial<LeagueNotificationPreference>
  ) => {
    setLeaguePrefs((prev) =>
      prev.map((league) => (league.league_id === leagueId ? { ...league, ...patch } : league))
    );
  };

  const handleReplayGuide = () => {
    if (!user) return;
    restartGuide(user.id);
    navigate("/", { replace: true });
  };

  const handleLogoutAll = async () => {
    setSecurityMessage(null);
    try {
      await logoutAll();
      navigate("/login", { replace: true });
    } catch (error) {
      setSecurityMessage(error instanceof Error ? error.message : "Unable to sign out of all devices.");
    }
  };

  const copySupportEmail = async () => {
    try {
      await navigator.clipboard.writeText(supportEmail);
      setSupportCopyState("copied");
    } catch {
      setSupportCopyState("error");
    }
  };

  if (isBootstrapping) {
    return (
      <div className="flex min-h-[45vh] items-center justify-center">
        <p className="text-[11px] font-black uppercase tracking-[0.22em] text-sky-200">
          Loading settings...
        </p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-4xl space-y-12 animate-in fade-in slide-in-from-bottom-4 duration-1000 pb-20 pt-12">
        <div className="space-y-6 border-b border-border/40 pb-12">
          <h1 className="text-5xl font-black uppercase italic tracking-tight text-foreground sm:text-7xl">
            Settings
          </h1>
          <p className="max-w-2xl text-xl font-medium leading-relaxed text-muted-foreground">
            Review app information and sign in to manage your account, notifications, and league preferences.
          </p>
        </div>

        <SettingsSection
          title="Account Settings"
          description="Sign in to personalize your experience"
          icon={User}
        >
          <div className="space-y-5">
            <p className="text-sm font-medium leading-relaxed text-muted-foreground">
              Account, notification, and league settings are saved to your manager profile after you sign in.
            </p>
            <Button
              className="h-12 rounded-2xl bg-primary px-7 text-[10px] font-black uppercase tracking-[0.2em] text-primary-foreground"
              onClick={() => navigate("/login", { state: { from: "/settings" } })}
            >
              Sign In To Manage Settings
            </Button>
          </div>
        </SettingsSection>

        <SettingsSection
          title="Support & Policies"
          description="Helpful links and account resources"
          icon={Shield}
        >
          <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-primary">Email Support</p>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <a
                href={`mailto:${supportEmail}`}
                className="break-all text-sm font-black text-foreground underline decoration-primary/50 underline-offset-4 transition hover:text-primary"
              >
                {supportEmail}
              </a>
              <Button
                type="button"
                variant="outline"
                onClick={() => void copySupportEmail()}
                className="shrink-0 rounded-xl border-primary/25 text-[10px] font-black uppercase tracking-[0.16em]"
                aria-live="polite"
              >
                <Copy className="mr-2 h-3.5 w-3.5" />
                {supportCopyState === "copied" ? "Copied" : supportCopyState === "error" ? "Copy Failed" : "Copy Email"}
              </Button>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {privacyPolicyUrl ? (
              <a
                href={privacyPolicyUrl}
                target="_blank"
                rel="noreferrer"
                className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary hover:bg-primary/10"
              >
                Privacy Policy
              </a>
            ) : null}
            {termsUrl ? (
              <a
                href={termsUrl}
                target="_blank"
                rel="noreferrer"
                className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary hover:bg-primary/10"
              >
                Terms
              </a>
            ) : null}
            {providerDisclosureUrl ? (
              <a
                href={providerDisclosureUrl}
                target="_blank"
                rel="noreferrer"
                className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary hover:bg-primary/10"
              >
                Provider Disclosure
              </a>
            ) : null}
          </div>
        </SettingsSection>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-12 animate-in fade-in slide-in-from-bottom-4 duration-1000 pb-20">
      {/* Header Section */}
      <div className="space-y-6 pt-12 relative border-b border-border/40 pb-12">
        <div className="flex items-center justify-between">
          <h1 className="text-7xl font-black tracking-tight text-foreground uppercase italic bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-transparent">
            Settings
          </h1>
          <Button
            className="bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase h-14 px-10 rounded-2xl shadow-[0_10px_30px_rgba(var(--primary),0.2)] hover:scale-105 transition-all duration-300"
            onClick={handleSave}
            disabled={saveState === "saving"}
          >
            <Save className="w-4 h-4 mr-3" />
            {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : "Save Changes"}
          </Button>
        </div>
        <p className="text-muted-foreground text-xl font-medium max-w-2xl leading-relaxed">
          Update your preferences, notification settings, and <span className="text-primary italic font-black uppercase">ESPN-style</span> theme selection.
        </p>
      </div>

      <div className="space-y-12">
        {/* PROFILE SECTION */}
        <SettingsSection 
          title="Account Profile" 
          description="Your active manager identity"
          icon={User}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
            <div className="space-y-4">
              <Label className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">Manager Name</Label>
              <p className="rounded-2xl border border-border bg-white/5 px-4 py-4 text-xs font-bold tracking-wider text-foreground">
                {user.firstName || "Manager"}
              </p>
            </div>
            <div className="space-y-4">
              <Label className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">Email Address</Label>
              <p className="rounded-2xl border border-border bg-white/5 px-4 py-4 text-xs font-bold tracking-wider text-foreground">
                {user.email}
              </p>
            </div>
          </div>
        </SettingsSection>

        {/* NOTIFICATIONS SECTION */}
        <SettingsSection 
          title="Notifications" 
          description="Manage how you receive updates and alerts"
          icon={Bell}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <SettingItem label="Push Notifications" description="Receive mobile push alerts">
              <Switch
                checked={prefs.push_enabled}
                onCheckedChange={(value) => setPrefs((prev) => ({ ...prev, push_enabled: value }))}
              />
            </SettingItem>
            <SettingItem label="Email Alerts" description="Send notifications to your email">
              <Switch
                checked={prefs.email_enabled}
                onCheckedChange={(value) => setPrefs((prev) => ({ ...prev, email_enabled: value }))}
              />
            </SettingItem>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <CheckboxItem 
              id="draft-alerts" 
              label="Draft alerts" 
              description="1 hour and live draft start reminders"
              checked={prefs.draft_alerts}
              onCheckedChange={(value: boolean | "indeterminate") =>
                setPrefs((prev) => ({ ...prev, draft_alerts: value === true }))
              }
            />
            <CheckboxItem 
              id="injury-alerts" 
              label="Injury alerts" 
              description="Real-time updates on your player status"
              checked={prefs.injury_alerts}
              onCheckedChange={(value: boolean | "indeterminate") =>
                setPrefs((prev) => ({ ...prev, injury_alerts: value === true }))
              }
            />
            <CheckboxItem 
              id="touchdown-alerts" 
              label="Touchdown alerts" 
              description="Instant scoring updates during games"
              checked={prefs.touchdown_alerts}
              onCheckedChange={(value: boolean | "indeterminate") =>
                setPrefs((prev) => ({ ...prev, touchdown_alerts: value === true }))
              }
            />
            <CheckboxItem 
              id="usage-alerts" 
              label="Usage spike alerts" 
              description="Alerts when a player sees a big workload jump"
              checked={prefs.usage_alerts}
              onCheckedChange={(value: boolean | "indeterminate") =>
                setPrefs((prev) => ({ ...prev, usage_alerts: value === true }))
              }
            />
            <CheckboxItem 
              id="waiver-alerts" 
              label="Waiver breakout alerts" 
              description="Notify when a player is trending up on waivers"
              checked={prefs.waiver_alerts}
              onCheckedChange={(value: boolean | "indeterminate") =>
                setPrefs((prev) => ({ ...prev, waiver_alerts: value === true }))
              }
            />
            <CheckboxItem 
              id="projection-alerts" 
              label="Projection change alerts" 
              description="Notifications when projections shift significantly"
              checked={prefs.projection_alerts}
              onCheckedChange={(value: boolean | "indeterminate") =>
                setPrefs((prev) => ({ ...prev, projection_alerts: value === true }))
              }
            />
            <CheckboxItem 
              id="lineup-reminders" 
              label="Lineup reminders" 
              description="Don't forget to set your weekly roster"
              checked={prefs.lineup_reminders}
              onCheckedChange={(value: boolean | "indeterminate") =>
                setPrefs((prev) => ({ ...prev, lineup_reminders: value === true }))
              }
            />
          </div>
          {saveState === "error" && (
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-red-400">
              Unable to save preferences.
            </p>
          )}
          {loadError ? <p role="alert" className="text-sm font-semibold text-red-300">{loadError}</p> : null}
          <div className="space-y-4 border-t border-border/40 pt-8">
            <h4 className="text-[10px] font-black tracking-[0.3em] text-primary uppercase">
              League Notification Controls
            </h4>
            <p className="text-[11px] font-medium text-muted-foreground/60 uppercase tracking-widest">
              Enable alerts per league and choose injury, big play, or projection updates.
            </p>
            {leaguePrefs.length === 0 && (
              <div className="p-5 rounded-2xl border border-border/50 bg-white/5">
                <p className="text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">
                  Join or create a league to manage league-specific alerts.
                </p>
              </div>
            )}
            {leaguePrefs.map((league) => (
              <div
                key={league.league_id}
                className="p-5 rounded-2xl border border-border/60 bg-white/[0.03] space-y-4"
              >
                <div className="flex items-center justify-between gap-5">
                  <div className="space-y-1">
                    <p className="text-[12px] font-black italic uppercase tracking-wide text-foreground">
                      {league.league_name || `League ${league.league_id}`}
                    </p>
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/60 font-bold">
                      League Alerts
                    </p>
                  </div>
                  <Switch
                    checked={league.enabled}
                    onCheckedChange={(value) =>
                      setLeaguePreference(league.league_id, { enabled: value })
                    }
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <CheckboxItem
                    id={`league-${league.league_id}-injury`}
                    label="Injury updates"
                    description="Player status changes"
                    checked={league.injury_alerts}
                    disabled={!league.enabled}
                    onCheckedChange={(value: boolean | "indeterminate") =>
                      setLeaguePreference(league.league_id, { injury_alerts: value === true })
                    }
                  />
                  <CheckboxItem
                    id={`league-${league.league_id}-big-play`}
                    label="Big play alerts"
                    description="Touchdowns and explosive plays"
                    checked={league.big_play_alerts}
                    disabled={!league.enabled}
                    onCheckedChange={(value: boolean | "indeterminate") =>
                      setLeaguePreference(league.league_id, { big_play_alerts: value === true })
                    }
                  />
                  <CheckboxItem
                    id={`league-${league.league_id}-projection`}
                    label="Projection updates"
                    description="Meaningful projection changes"
                    checked={league.projection_alerts}
                    disabled={!league.enabled}
                    onCheckedChange={(value: boolean | "indeterminate") =>
                      setLeaguePreference(league.league_id, { projection_alerts: value === true })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </SettingsSection>

        {/* PREFERENCES SECTION */}
        <SettingsSection 
          title="App Preferences" 
          description="Customize your viewing experience"
          icon={Sliders}
        >
          <div className="space-y-10">
            <SettingItem 
              label="Default Active League"
              description="Choose which league opens first across roster/waiver/watchlist views"
            >
              <Select
                value={activeLeagueId ? String(activeLeagueId) : ""}
                onValueChange={(value) => setActiveLeagueId(Number(value))}
              >
                <SelectTrigger className="w-60 bg-white/5 border-border rounded-2xl h-14 focus:ring-primary/20 focus:border-primary/40 transition-all text-xs font-bold tracking-wider uppercase">
                  <SelectValue placeholder="Select league" />
                </SelectTrigger>
                <SelectContent className="bg-[#0A0C10] border-border rounded-2xl">
                  {leagues.map((league) => (
                    <SelectItem
                      key={league.id}
                      value={String(league.id)}
                      className="text-xs font-bold uppercase tracking-widest focus:bg-primary focus:text-primary-foreground"
                    >
                      {league.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </SettingItem>

            <SettingItem
              label="Replay App Guide"
              description="Start the onboarding walkthrough again at any time"
            >
              <Button
                variant="outline"
                className="h-12 px-6 rounded-2xl border-primary/20 bg-primary/5 text-[10px] font-black uppercase tracking-[0.2em] text-primary hover:bg-primary/10"
                onClick={handleReplayGuide}
                disabled={!user}
              >
                Start Guide Again
              </Button>
            </SettingItem>
          </div>
        </SettingsSection>

        {/* SECURITY SECTION */}
        <SettingsSection 
          title="Security & Privacy" 
          description="Keep your account safe and secure"
          icon={Shield}
        >
          <div className="space-y-8">
            <div className="rounded-3xl border border-primary/15 bg-primary/[0.04] p-6">
              <h3 className="text-sm font-black uppercase tracking-[0.16em] text-foreground">Change Password</h3>
              <p className="mt-2 text-sm font-medium text-muted-foreground">
                Enter your current password, then choose a new password. You will be signed out on every device.
              </p>
              <div className="mt-5">
                <PasswordChangeForm
                  mode="authenticated"
                  onSuccess={() => navigate("/login", { replace: true, state: { passwordResetSuccess: true } })}
                />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {privacyPolicyUrl ? (
                <a
                  href={privacyPolicyUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary hover:bg-primary/10"
                >
                  Privacy Policy
                </a>
              ) : null}
              {termsUrl ? (
                <a
                  href={termsUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary hover:bg-primary/10"
                >
                  Terms
                </a>
              ) : null}
              {providerDisclosureUrl ? (
                <a
                  href={providerDisclosureUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary hover:bg-primary/10"
                >
                  Provider Disclosure
                </a>
              ) : null}
              {supportEmail ? (
                <a
                  href={`mailto:${supportEmail}`}
                  className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary hover:bg-primary/10"
                >
                  Contact Support
                </a>
              ) : null}
            </div>

            <div className="flex justify-center pt-8">
               <Button type="button" variant="ghost" onClick={() => void handleLogoutAll()} className="text-muted-foreground hover:text-red-400 gap-3 text-[11px] font-black uppercase tracking-[0.2em]">
                  <LogOut className="w-4 h-4" />
                  Sign Out of All Devices
               </Button>
            </div>
            {securityMessage ? <p role="alert" className="text-sm font-semibold text-red-300">{securityMessage}</p> : null}
          </div>
        </SettingsSection>
      </div>
    </div>
  );
}
