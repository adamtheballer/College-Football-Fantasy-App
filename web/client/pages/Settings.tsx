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
import { isExternalLegalHref, resolveLegalDocumentHref } from "@/lib/legal-links";

const SettingsSection = ({ title, description, children, icon: Icon }: any) => (
  <Card className="overflow-hidden rounded-lg border-border bg-card shadow-none">
    <CardHeader className="border-b border-border px-4 py-4 sm:px-5">
      <div className="flex items-start gap-3 sm:items-center sm:gap-6">
        <div className="rounded-md bg-primary/10 p-2 text-primary">
          <Icon className="h-4 w-4 sm:h-5 sm:w-5" />
        </div>
        <div className="min-w-0 space-y-1">
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.16em] text-primary">{title}</CardTitle>
          <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">{description}</p>
        </div>
      </div>
    </CardHeader>
    <CardContent className="space-y-5 p-4 sm:p-5">
      {children}
    </CardContent>
  </Card>
);

const PolicyLinks = ({
  privacyPolicyUrl,
  termsUrl,
  supportEmail,
}: {
  privacyPolicyUrl?: string | null;
  termsUrl?: string | null;
  supportEmail?: string | null;
}) => {
  type PolicyLink = { href: string; label: string; external?: boolean };
  const linkCandidates: Array<PolicyLink | null> = [
    { href: resolveLegalDocumentHref(privacyPolicyUrl, "privacy"), label: "Privacy Policy" },
    { href: resolveLegalDocumentHref(termsUrl, "terms"), label: "Terms" },
    supportEmail ? { href: `mailto:${supportEmail}`, label: "Contact Support", external: false } : null,
  ];
  const links = linkCandidates
    .filter((link): link is PolicyLink => link !== null)
    .map((link) => ({ ...link, external: link.external ?? isExternalLegalHref(link.href) }));

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {links.map((link) => (
        <a
          key={link.label}
          href={link.href}
          target={link.external ? "_blank" : undefined}
          rel={link.external ? "noreferrer" : undefined}
          className="rounded-md border border-border bg-muted/30 px-4 py-3 text-[10px] font-black uppercase tracking-[0.14em] text-primary hover:bg-muted"
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
      <Label className="text-sm font-bold text-foreground">{label}</Label>
      {description && <p className="text-[11px] font-medium leading-relaxed text-muted-foreground">{description}</p>}
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

  const handleConfirmPhoto = async () => {
    if (!pendingAvatarUrl) return;
    const confirmedAvatarUrl = pendingAvatarUrl;
    const previousAvatarUrl = avatarUrl;

    // Commit the preview before the request resolves. This makes the new
    // picture visible the instant the user confirms it, while the server save
    // continues in the background. If persistence fails, restore the prior
    // avatar and explain that it was not changed.
    setAvatarUrl(confirmedAvatarUrl);
    setPendingAvatarUrl(null);
    setPendingAvatarName(null);
    setAvatarPreviewError(false);
    setPhotoState("saving");
    setProfileError(null);
    try {
      const updatedUser = await updateProfile({ avatarUrl: confirmedAvatarUrl });
      setAvatarUrl(updatedUser.avatarUrl ?? confirmedAvatarUrl);
    } catch (error) {
      setAvatarUrl(previousAvatarUrl);
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
      <div className="mx-auto max-w-4xl space-y-6 pb-24 pt-6 sm:pb-20 sm:pt-10">
        <div className="space-y-3 border-b border-border pb-6">
          <h1 className="cfb-display-title text-3xl text-foreground sm:text-4xl">
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
              className="h-10 rounded-md bg-primary px-5 text-[10px] font-black uppercase tracking-[0.14em] text-primary-foreground shadow-none"
              onClick={() => navigate("/login", { state: { from: "/settings" } })}
            >
              Sign In To Manage Settings
            </Button>
          </div>
        </SettingsSection>

        <section id="support" className="scroll-mt-8">
          <SettingsSection
            title="Support & Policies"
            description="Helpful links and account resources"
            icon={Shield}
          >
          <SupportContactCard />
          <PolicyLinks privacyPolicyUrl={privacyPolicyUrl} termsUrl={termsUrl} supportEmail={supportEmail} />
          </SettingsSection>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-24 sm:pb-20">
      {/* Header Section */}
      <div className="space-y-3 border-b border-border pb-6 pt-6 sm:pt-10">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="cfb-display-title text-3xl text-foreground sm:text-4xl">
            Settings
          </h1>
          <Button
            className="h-10 w-full rounded-md bg-primary px-5 text-[10px] font-black uppercase tracking-[0.14em] text-primary-foreground shadow-none sm:w-auto"
            onClick={handleSave}
            disabled={saveState === "saving" || photoState === "saving"}
          >
            <Save className="w-4 h-4 mr-3" />
            {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : "Save Changes"}
          </Button>
        </div>
        <p className="max-w-2xl text-sm font-medium leading-relaxed text-muted-foreground sm:text-base">
          Update your manager profile and choose which league opens first across the app.
        </p>
      </div>

      <div className="space-y-6">
        {/* PROFILE SECTION */}
        <SettingsSection 
          title="Account Profile" 
          description="Your active manager identity"
          icon={User}
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-[10px] font-black tracking-[0.14em] text-muted-foreground uppercase">Manager Name</Label>
              <Input
                aria-label="Manager Name"
                value={managerName}
                maxLength={100}
                onChange={(event) => setManagerName(event.target.value)}
                className="h-10 rounded-md border-border bg-background px-3 text-sm font-semibold text-foreground"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[10px] font-black tracking-[0.14em] text-muted-foreground uppercase">Email Address</Label>
              <p className="rounded-md border border-border bg-background px-3 py-3 text-xs font-semibold text-foreground">
                {user.email}
              </p>
            </div>
          </div>
          <div className="grid gap-4 rounded-lg border border-border bg-muted/20 p-4 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center">
            <ManagerAvatar
              key={pendingAvatarUrl ?? (avatarUrl.trim() || "manager-avatar-initials")}
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
                accept="image/*"
                className="sr-only"
                onChange={handlePhotoChosen}
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" className="h-9 rounded-md border-border text-[10px] font-black uppercase tracking-[0.12em]" onClick={() => photoInputRef.current?.click()} disabled={photoState !== "idle"}>
                  <ImagePlus className="mr-2 h-4 w-4" />
                  {photoState === "preparing" ? "Preparing..." : "Choose Photo"}
                </Button>
                {pendingAvatarUrl ? <Button type="button" className="h-9 rounded-md px-4 text-[10px] font-black uppercase tracking-[0.12em]" onClick={handleConfirmPhoto} disabled={photoState !== "idle"}>Confirm Photo</Button> : null}
                {pendingAvatarUrl ? <Button type="button" variant="ghost" className="h-9 rounded-md text-[10px] font-black uppercase tracking-[0.12em]" onClick={() => { setPendingAvatarUrl(null); setPendingAvatarName(null); setAvatarPreviewError(false); }} disabled={photoState !== "idle"}>Cancel</Button> : null}
                {(avatarUrl.trim() || user.avatarUrl) && !pendingAvatarUrl ? <Button type="button" variant="outline" className="h-9 rounded-md border-border text-[10px] font-black uppercase tracking-[0.12em]" onClick={handleRemovePhoto} disabled={photoState !== "idle"}>Remove Picture</Button> : null}
              </div>
              {pendingAvatarUrl ? <p className="text-xs font-medium text-primary">{pendingAvatarName ?? "Selected photo"} is ready. Tap Confirm Photo to update your profile picture.</p> : null}
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
                  className="mt-3 h-10 rounded-md border-border bg-background px-3 text-sm text-foreground"
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
          <div className="space-y-5">
            <SettingItem 
              label="Default Active League"
              description="Choose which league opens first across roster/waiver/watchlist views"
            >
              <Select
                value={activeLeagueId ? String(activeLeagueId) : ""}
                onValueChange={(value) => setActiveLeagueId(Number(value))}
              >
                <SelectTrigger className="h-10 w-full rounded-md border-border bg-background text-xs font-semibold sm:w-60">
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
                className="h-10 rounded-md border-border bg-muted/30 px-5 text-[10px] font-black uppercase tracking-[0.14em] text-primary hover:bg-muted"
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
          <div className="space-y-5">
            <div className="rounded-lg border border-border bg-muted/20 p-4">
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
            <PolicyLinks privacyPolicyUrl={privacyPolicyUrl} termsUrl={termsUrl} supportEmail={supportEmail} />

            <div className="flex justify-center pt-3">
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
