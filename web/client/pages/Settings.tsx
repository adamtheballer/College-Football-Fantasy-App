import React, { useEffect, useRef, useState } from "react";
import { User, Sliders, Shield, Save, LogOut, ImagePlus } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/use-auth";
import { restartGuide } from "@/lib/onboarding";
import { useLeagues } from "@/hooks/use-leagues";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { PasswordChangeForm } from "@/components/auth/PasswordChangeForm";
import { useRuntimeCapabilities } from "@/components/RuntimeCompatibilityGate";
import { SupportContactCard } from "@/components/support/SupportContactCard";
import { NotificationSettingsPanel } from "@/components/NotificationSettingsPanel";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { prepareProfileImage } from "@/lib/profileImage";

const SettingsSection = ({ title, description, children, icon: Icon }: any) => (
  <Card className="group relative overflow-hidden rounded-3xl border-border/60 bg-card/40 shadow-[0_20px_50px_rgba(0,0,0,0.3)] backdrop-blur-md transition-all duration-700 hover:border-primary/20 sm:rounded-[2.5rem]">
    <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors" />
    <CardHeader className="relative z-10 border-b border-border/40 bg-gradient-to-br from-white/5 to-transparent px-5 pt-5 sm:px-10 sm:pt-10">
      <div className="flex items-start gap-3 sm:items-center sm:gap-6">
        <div className="rounded-2xl bg-primary/10 p-3 text-primary shadow-[0_0_20px_rgba(var(--primary),0.1)] transition-all duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground sm:p-4">
          <Icon className="h-5 w-5 sm:h-6 sm:w-6" />
        </div>
        <div className="min-w-0 space-y-1">
          <CardTitle className="text-[10px] font-black uppercase tracking-[0.22em] text-primary sm:tracking-[0.3em]">{title}</CardTitle>
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground/60 sm:text-[11px] sm:tracking-widest">{description}</p>
        </div>
      </div>
    </CardHeader>
    <CardContent className="relative z-10 space-y-6 p-5 sm:space-y-8 sm:p-10">
      {children}
    </CardContent>
  </Card>
);

const PolicyLinks = ({
  privacyPolicyUrl,
  termsUrl,
  providerDisclosureUrl,
  supportEmail,
}: {
  privacyPolicyUrl?: string | null;
  termsUrl?: string | null;
  providerDisclosureUrl?: string | null;
  supportEmail?: string | null;
}) => {
  const links = [
    privacyPolicyUrl ? { href: privacyPolicyUrl, label: "Privacy Policy", external: true } : null,
    termsUrl ? { href: termsUrl, label: "Terms", external: true } : null,
    providerDisclosureUrl ? { href: providerDisclosureUrl, label: "Provider Disclosure", external: true } : null,
    supportEmail ? { href: `mailto:${supportEmail}`, label: "Contact Support", external: false } : null,
  ].filter((link): link is { href: string; label: string; external: boolean } => link !== null);

  if (!links.length) return null;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {links.map((link) => (
        <a
          key={link.label}
          href={link.href}
          target={link.external ? "_blank" : undefined}
          rel={link.external ? "noreferrer" : undefined}
          className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary hover:bg-primary/10"
        >
          {link.label}
        </a>
      ))}
    </div>
  );
};

const SettingItem = ({ label, description, children }: any) => (
  <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-10">
    <div className="min-w-0 space-y-1">
      <Label className="text-sm font-black italic uppercase tracking-tight text-foreground">{label}</Label>
      {description && <p className="text-[11px] font-medium leading-relaxed text-muted-foreground/60">{description}</p>}
    </div>
    <div className="w-full shrink-0 sm:w-auto">
      {children}
    </div>
  </div>
);

export default function Settings() {
  const navigate = useNavigate();
  const { user, isBootstrapping, logoutAll, updateProfile } = useAuth();
  const {
    privacy_policy_url: privacyPolicyUrl,
    terms_url: termsUrl,
    provider_disclosure_url: providerDisclosureUrl,
    support_email: supportEmail,
  } = useRuntimeCapabilities();
  const { data: leagues = [] } = useLeagues(50, Boolean(user));
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [managerName, setManagerName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [pendingAvatarUrl, setPendingAvatarUrl] = useState<string | null>(null);
  const [pendingAvatarName, setPendingAvatarName] = useState<string | null>(null);
  const [photoState, setPhotoState] = useState<"idle" | "preparing" | "saving">("idle");
  const [avatarPreviewError, setAvatarPreviewError] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [securityMessage, setSecurityMessage] = useState<string | null>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setManagerName(user?.firstName ?? "");
    setAvatarUrl(user?.avatarUrl ?? "");
    setPendingAvatarUrl(null);
    setPendingAvatarName(null);
    setPhotoState("idle");
    setAvatarPreviewError(false);
    setProfileError(null);
  }, [user]);

  const handleSave = async () => {
    if (!user) return;
    const nextName = managerName.trim();
    const nextAvatarUrl = avatarUrl.trim();
    if (!nextName) {
      setProfileError("Manager name is required.");
      setSaveState("error");
      return;
    }
    setSaveState("saving");
    setProfileError(null);
    try {
      await updateProfile({ firstName: nextName, avatarUrl: nextAvatarUrl || null });
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 1500);
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to save your profile picture. Your previous picture is still active.");
      setSaveState("error");
    }
  };

  const handleReplayGuide = () => {
    if (!user) return;
    restartGuide(user.id);
    navigate("/", { state: { replayGuide: true } });
  };

  const handlePhotoChosen = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const photo = event.target.files?.[0];
    // Reset first so choosing the same image again emits a change event.
    event.target.value = "";
    if (!photo) return;

    setPhotoState("preparing");
    setProfileError(null);
    setAvatarPreviewError(false);
    try {
      const preparedPhoto = await prepareProfileImage(photo);
      setPendingAvatarUrl(preparedPhoto);
      setPendingAvatarName(photo.name);
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to prepare this photo.");
    } finally {
      setPhotoState("idle");
    }
  };

  const handleSelectPhoto = async () => {
    if (!pendingAvatarUrl) return;
    setPhotoState("saving");
    setProfileError(null);
    try {
      const updatedUser = await updateProfile({ avatarUrl: pendingAvatarUrl });
      setAvatarUrl(updatedUser.avatarUrl ?? pendingAvatarUrl);
      setPendingAvatarUrl(null);
      setPendingAvatarName(null);
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to update your profile picture. Your previous picture is still active.");
    } finally {
      setPhotoState("idle");
    }
  };

  const handleRemovePhoto = async () => {
    setPendingAvatarUrl(null);
    setPendingAvatarName(null);
    setAvatarPreviewError(false);
    setPhotoState("saving");
    setProfileError(null);
    try {
      await updateProfile({ avatarUrl: null });
      setAvatarUrl("");
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to remove your profile picture. Your previous picture is still active.");
    } finally {
      setPhotoState("idle");
    }
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
      <div className="mx-auto max-w-4xl space-y-8 animate-in fade-in slide-in-from-bottom-4 pb-24 pt-6 duration-1000 sm:space-y-12 sm:pb-20 sm:pt-12">
        <div className="space-y-6 border-b border-border/40 pb-12">
          <h1 className="text-5xl font-black uppercase italic tracking-tight text-foreground sm:text-7xl">
            Settings
          </h1>
          <p className="max-w-2xl text-lg font-medium leading-relaxed text-muted-foreground sm:text-xl">
            Review app information and sign in to manage your account and league preferences.
          </p>
        </div>

        <SettingsSection
          title="Account Settings"
          description="Sign in to personalize your experience"
          icon={User}
        >
          <div className="space-y-5">
            <p className="text-sm font-medium leading-relaxed text-muted-foreground">
              Account and league preferences are available after you sign in.
            </p>
            <Button
              className="h-12 rounded-2xl bg-primary px-7 text-[10px] font-black uppercase tracking-[0.2em] text-primary-foreground"
              onClick={() => navigate("/login", { state: { from: "/settings" } })}
            >
              Sign In To Manage Settings
            </Button>
          </div>
        </SettingsSection>

        {privacyPolicyUrl || termsUrl || providerDisclosureUrl || supportEmail ? <section id="support" className="scroll-mt-8">
          <SettingsSection
            title="Support & Policies"
            description="Helpful links and account resources"
            icon={Shield}
          >
          <SupportContactCard />
          <PolicyLinks privacyPolicyUrl={privacyPolicyUrl} termsUrl={termsUrl} providerDisclosureUrl={providerDisclosureUrl} supportEmail={supportEmail} />
          </SettingsSection>
        </section>
        : null}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 animate-in fade-in slide-in-from-bottom-4 pb-24 duration-1000 sm:space-y-12 sm:pb-20">
      {/* Header Section */}
      <div className="relative space-y-4 border-b border-border/40 pb-7 pt-6 sm:space-y-6 sm:pb-12 sm:pt-12">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-4xl font-black italic uppercase tracking-tight text-transparent sm:text-6xl lg:text-7xl">
            Settings
          </h1>
          <Button
            className="h-12 w-full rounded-2xl bg-primary px-6 text-[10px] font-black uppercase tracking-[0.18em] text-primary-foreground shadow-[0_10px_30px_rgba(var(--primary),0.2)] transition-all duration-300 hover:scale-[1.02] sm:h-14 sm:w-auto sm:px-10 sm:tracking-[0.2em] sm:hover:scale-105"
            onClick={handleSave}
            disabled={saveState === "saving" || photoState === "saving"}
          >
            <Save className="w-4 h-4 mr-3" />
            {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : "Save Changes"}
          </Button>
        </div>
        <p className="max-w-2xl text-base font-medium leading-relaxed text-muted-foreground sm:text-xl">
          Update your manager profile and choose which league opens first across the app.
        </p>
      </div>

      <div className="space-y-12">
        {/* PROFILE SECTION */}
        <SettingsSection 
          title="Account Profile" 
          description="Your active manager identity"
          icon={User}
        >
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 md:gap-10">
            <div className="space-y-4">
              <Label className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">Manager Name</Label>
              <Input
                aria-label="Manager Name"
                value={managerName}
                maxLength={100}
                onChange={(event) => setManagerName(event.target.value)}
                className="h-12 rounded-2xl border-border bg-white/5 px-4 text-sm font-bold tracking-wide text-foreground"
              />
            </div>
            <div className="space-y-4">
              <Label className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">Email Address</Label>
              <p className="rounded-2xl border border-border bg-white/5 px-4 py-4 text-xs font-bold tracking-wider text-foreground">
                {user.email}
              </p>
            </div>
          </div>
          <div className="grid gap-5 rounded-2xl border border-border/70 bg-black/10 p-5 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center">
            <ManagerAvatar
              avatarUrl={pendingAvatarUrl ?? (avatarUrl.trim() || null)}
              managerName={managerName}
              size="xl"
              eager
              onImageError={() => setAvatarPreviewError(true)}
              onImageLoad={() => setAvatarPreviewError(false)}
            />
            <div className="min-w-0 space-y-3">
              <div>
                <Label className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">Manager Profile Picture</Label>
                <p className="mt-1 text-xs text-muted-foreground">Choose a photo from your device. Your phone handles photo permission and lets you choose the photos to share.</p>
              </div>
              <input
                ref={photoInputRef}
                aria-label="Choose a profile photo"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={handlePhotoChosen}
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" className="h-10 rounded-xl border-border text-[10px] font-black uppercase tracking-[0.14em]" onClick={() => photoInputRef.current?.click()} disabled={photoState !== "idle"}>
                  <ImagePlus className="mr-2 h-4 w-4" />
                  {photoState === "preparing" ? "Preparing..." : "Choose Photo"}
                </Button>
                {pendingAvatarUrl ? <Button type="button" className="h-10 rounded-xl px-4 text-[10px] font-black uppercase tracking-[0.14em]" onClick={handleSelectPhoto} disabled={photoState !== "idle"}>Select Photo</Button> : null}
                {pendingAvatarUrl ? <Button type="button" variant="ghost" className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.14em]" onClick={() => { setPendingAvatarUrl(null); setPendingAvatarName(null); setAvatarPreviewError(false); }} disabled={photoState !== "idle"}>Cancel</Button> : null}
                {(avatarUrl.trim() || user.avatarUrl) && !pendingAvatarUrl ? <Button type="button" variant="outline" className="h-10 rounded-xl border-border text-[10px] font-black uppercase tracking-[0.14em]" onClick={handleRemovePhoto} disabled={photoState !== "idle"}>Remove Picture</Button> : null}
              </div>
              {pendingAvatarUrl ? <p className="text-xs font-medium text-primary">{pendingAvatarName ?? "Selected photo"} is ready. Tap Select Photo to update your profile picture.</p> : null}
              {avatarPreviewError ? <p role="alert" className="text-xs font-medium text-red-300">This image could not be loaded. Choose a different photo.</p> : null}
              <details className="pt-1">
                <summary className="cursor-pointer text-xs font-medium text-muted-foreground">Use an image address instead</summary>
                <Input
                  id="profile-image-url"
                  aria-label="Profile image URL (optional)"
                  type="url"
                  inputMode="url"
                  autoComplete="url"
                  maxLength={2048}
                  placeholder="https://example.com/profile-picture.jpg"
                  value={avatarUrl.startsWith("data:") ? "" : avatarUrl}
                  onChange={(event) => {
                    setAvatarUrl(event.target.value);
                    setPendingAvatarUrl(null);
                    setPendingAvatarName(null);
                    setAvatarPreviewError(false);
                  }}
                  className="mt-3 h-12 rounded-xl border-border bg-white/5 px-4 text-sm text-foreground"
                />
              </details>
            </div>
          </div>
          {profileError ? <p role="alert" className="text-sm font-semibold text-red-300">{profileError}</p> : null}
        </SettingsSection>

        {/* PREFERENCES SECTION */}
        <SettingsSection 
          title="App Preferences" 
          description="Customize your viewing experience"
          icon={Sliders}
        >
          <div className="space-y-8">
            <SettingItem 
              label="Default Active League"
              description="Choose which league opens first across roster/waiver/watchlist views"
            >
              <Select
                value={activeLeagueId ? String(activeLeagueId) : ""}
                onValueChange={(value) => setActiveLeagueId(Number(value))}
              >
                <SelectTrigger className="h-12 w-full rounded-2xl border-border bg-white/5 text-xs font-bold uppercase tracking-wider transition-all focus:border-primary/40 focus:ring-primary/20 sm:h-14 sm:w-60">
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

        <NotificationSettingsPanel />

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
            <PolicyLinks privacyPolicyUrl={privacyPolicyUrl} termsUrl={termsUrl} providerDisclosureUrl={providerDisclosureUrl} supportEmail={supportEmail} />

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
