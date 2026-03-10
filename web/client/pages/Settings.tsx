import React, { useEffect, useState } from "react";
import { User, Bell, Sliders, Shield, Save, LogOut } from "lucide-react";
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
import { apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { restartGuide } from "@/lib/onboarding";

type LeagueNotificationPreference = {
  league_id: number;
  league_name: string | null;
  enabled: boolean;
  injury_alerts: boolean;
  big_play_alerts: boolean;
  projection_alerts: boolean;
};

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
  const { user } = useAuth();
  const userKey = user?.id ? String(user.id) : "guest";
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [leaguePrefs, setLeaguePrefs] = useState<LeagueNotificationPreference[]>([]);
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
    apiGet<any>("/notifications/preferences", { user_key: userKey })
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
      .catch(() => {});
    apiGet<{ data: LeagueNotificationPreference[] }>("/notifications/league-preferences")
      .then((leaguePayload) => {
        setLeaguePrefs(leaguePayload?.data ?? []);
      })
      .catch(() => {
        setLeaguePrefs([]);
      });
  }, [user, userKey]);

  const handleSave = async () => {
    if (!user) return;
    setSaveState("saving");
    try {
      await apiPost("/notifications/preferences", { user_key: userKey, ...prefs });
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
    } catch {
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

  const teams = [
    "Alabama", "Georgia", "Ohio State", "Michigan", "Texas", "Florida State", "LSU", "Oregon"
  ];

  const handleReplayGuide = () => {
    if (!user) return;
    restartGuide(user.id);
    navigate("/", { replace: true });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-12 animate-in fade-in slide-in-from-bottom-4 duration-1000 relative z-10 pb-20">
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
          description="Personal information and public identity"
          icon={User}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
            <div className="space-y-4">
              <Label className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">Full Name</Label>
              <Input 
                placeholder="Adam Bajdechi" 
                className="bg-white/5 border-border rounded-2xl h-14 focus:ring-primary/20 focus:border-primary/40 transition-all text-xs font-bold tracking-wider"
              />
            </div>
            <div className="space-y-4">
              <Label className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">Email Address</Label>
              <Input 
                placeholder="adam@example.com" 
                className="bg-white/5 border-border rounded-2xl h-14 focus:ring-primary/20 focus:border-primary/40 transition-all text-xs font-bold tracking-wider"
              />
            </div>
          </div>
          <div className="flex items-center gap-8 p-6 rounded-3xl bg-primary/5 border border-primary/10">
             <div className="w-20 h-20 rounded-full bg-gradient-to-br from-primary to-blue-600 flex items-center justify-center text-3xl font-black italic text-white shadow-2xl">
                AB
             </div>
             <div className="space-y-2">
                <h4 className="text-sm font-black italic uppercase tracking-tight text-foreground">Profile Picture</h4>
                <p className="text-[11px] font-medium text-muted-foreground/60 uppercase tracking-widest">Recommended: 400x400px JPG or PNG</p>
                <div className="flex gap-4 mt-4">
                  <Button variant="outline" className="h-10 px-6 rounded-xl text-[9px] font-black uppercase tracking-widest border-primary/20 text-primary hover:bg-primary/10">Upload New</Button>
                  <Button variant="ghost" className="h-10 px-6 rounded-xl text-[9px] font-black uppercase tracking-widest text-red-400 hover:text-red-500 hover:bg-red-500/10">Remove</Button>
                </div>
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
              label="Favorite Team" 
              description="Personalize your dashboard with team colors"
            >
              <Select defaultValue="Alabama">
                <SelectTrigger className="w-60 bg-white/5 border-border rounded-2xl h-14 focus:ring-primary/20 focus:border-primary/40 transition-all text-xs font-bold tracking-wider uppercase">
                  <SelectValue placeholder="Select team" />
                </SelectTrigger>
                <SelectContent className="bg-[#0A0C10] border-border rounded-2xl">
                  {teams.map(team => (
                    <SelectItem key={team} value={team} className="text-xs font-bold uppercase tracking-widest focus:bg-primary focus:text-primary-foreground">
                      {team}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </SettingItem>

            <SettingItem 
              label="Theme Selection" 
              description="Choose between different visual styles"
            >
               <div className="flex bg-white/5 p-1.5 rounded-2xl border border-border">
                  <button className="px-6 py-3 rounded-xl bg-primary text-primary-foreground text-[9px] font-black uppercase tracking-[0.2em] shadow-lg transition-all">Modern</button>
                  <button className="px-6 py-3 rounded-xl text-muted-foreground hover:text-foreground text-[9px] font-black uppercase tracking-[0.2em] transition-all">ESPN Style</button>
               </div>
            </SettingItem>

            <SettingItem 
              label="Auto-Update Scores" 
              description="Automatically refresh live game data"
            >
               <div className="w-14 h-8 bg-primary/20 border border-primary/40 rounded-full relative cursor-pointer p-1 group">
                  <div className="w-6 h-6 bg-primary rounded-full shadow-[0_0_15px_rgba(var(--primary),0.4)] absolute right-1 group-hover:scale-110 transition-all" />
               </div>
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
            <div className="flex items-center justify-between p-6 rounded-3xl bg-red-500/5 border border-red-500/10">
              <div className="space-y-1">
                <h4 className="text-sm font-black italic uppercase tracking-tight text-foreground">Danger Zone</h4>
                <p className="text-[11px] font-medium text-muted-foreground/60 uppercase tracking-widest">Permanent actions that cannot be undone</p>
              </div>
              <Button variant="ghost" className="h-12 px-8 rounded-2xl text-[10px] font-black uppercase tracking-widest text-red-400 hover:text-white hover:bg-red-500 shadow-none border border-red-500/20">Delete Account</Button>
            </div>
            
            <div className="flex justify-center pt-8">
               <Button variant="ghost" className="text-muted-foreground hover:text-red-400 gap-3 text-[11px] font-black uppercase tracking-[0.2em]">
                  <LogOut className="w-4 h-4" />
                  Sign Out of All Devices
               </Button>
            </div>
          </div>
        </SettingsSection>
      </div>
    </div>
  );
}
