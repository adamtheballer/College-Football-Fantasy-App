import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { User, Sliders, Shield, Save, LogOut, ImagePlus, Trash2 } from "lucide-react";
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
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { useNameChangeEligibility } from "@/hooks/use-name-change-eligibility";
import { formatNameChangeWait } from "@/lib/name-change";
import { restartGuide } from "@/lib/onboarding";
import { useLeagues } from "@/hooks/use-leagues";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { PasswordChangeForm } from "@/components/auth/PasswordChangeForm";
import { useRuntimeCapabilities } from "@/components/RuntimeCompatibilityGate";
import { SupportContactCard } from "@/components/support/SupportContactCard";
import { NotificationSettingsPanel } from "@/components/NotificationSettingsPanel";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
  const { user, isBootstrapping, logoutAll, deleteAccount, updateProfile, requestPasswordResetForCurrentUser } = useAuth();
  const {
    privacy_policy_url: privacyPolicyUrl,
    terms_url: termsUrl,
    support_email: supportEmail,
    password_reset_enabled: passwordResetEnabled,
    password_reset_email_configured: passwordResetEmailConfigured,
  } = useRuntimeCapabilities();
  const { data: leagues = [] } = useLeagues(50, Boolean(user));
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [managerName, setManagerName] = useState("");
  const [isManagerNameFocused, setIsManagerNameFocused] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState("");
  const [pendingAvatarUrl, setPendingAvatarUrl] = useState<string | null>(null);
  const [pendingAvatarName, setPendingAvatarName] = useState<string | null>(null);
  const [photoState, setPhotoState] = useState<"idle" | "preparing" | "saving">("idle");
  const [avatarPreviewError, setAvatarPreviewError] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileErrorField, setProfileErrorField] = useState<"first_name" | "avatar_url" | null>(null);
  const eligibility = useNameChangeEligibility(user?.id ?? null, Boolean(user) && !isBootstrapping);
  const profileSaveRef = useRef<AbortController>();
  const accountIdRef = useRef(user?.id);
  const [pendingNameChange, setPendingNameChange] = useState<{ name: string; avatarUrl: string | null } | null>(null);
  const [securityMessage, setSecurityMessage] = useState<string | null>(null);
  const [isSendingReset, setIsSendingReset] = useState(false);
  const [accountDeletionOpen, setAccountDeletionOpen] = useState(false);
  const [accountDeletionPassword, setAccountDeletionPassword] = useState("");
  const [accountDeletionConfirmation, setAccountDeletionConfirmation] = useState("");
  const [accountDeletionError, setAccountDeletionError] = useState<string | null>(null);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const saveStateResetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (saveStateResetTimeoutRef.current) {
      clearTimeout(saveStateResetTimeoutRef.current);
    }
  }, []);

  useEffect(() => {
    setManagerName(user?.firstName ?? "");
    setAvatarUrl(user?.avatarUrl ?? "");
    setPendingAvatarUrl(null);
    setPendingAvatarName(null);
    setPhotoState("idle");
    setAvatarPreviewError(false);
    setProfileError(null);
    setProfileErrorField(null);

  }, [user]);

  useLayoutEffect(() => {
    accountIdRef.current = user?.id;
    setSaveState("idle");
    setPendingNameChange(null);
    return () => {
      accountIdRef.current = undefined;
      profileSaveRef.current?.abort();
      profileSaveRef.current = undefined;
      if (saveStateResetTimeoutRef.current) clearTimeout(saveStateResetTimeoutRef.current);
    };
  }, [user?.id]);

  const managerNameCooldownActive = eligibility.phase === "ready" && eligibility.timing?.can_change_name === false;
  const managerNameAvailableDateTime = eligibility.timing?.next_eligible_at
    ? new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit", timeZoneName: "short" }).format(new Date(eligibility.timing.next_eligible_at))
    : null;

  const showProfileError = (error: unknown, fallback: string, preferredField: "first_name" | "avatar_url" | null = null) => {
    const apiError = error instanceof ApiError ? error : null;
    const field = apiError?.field === "first_name" || apiError?.field === "avatar_url" ? apiError.field : preferredField;
    if (apiError?.code === "NAME_CHANGE_COOLDOWN") {
      if (apiError.nameChangeEligibility) eligibility.accept(apiError.nameChangeEligibility);
      void eligibility.refresh();
      setProfileError("Your name was not changed. This attempt did not restart the waiting period.");
    } else {
      setProfileError(error instanceof Error && error.message ? error.message : fallback);
    }
    setProfileErrorField(field);
  };

  // Only reconcile a newly fetched name when the manager has not started
  // editing. An earlier eligibility request cannot overwrite an in-flight save.
  const previousAuthoritativeName = useRef(user?.firstName ?? "");
  useEffect(() => {
    const name = eligibility.timing?.current_name;
    if (eligibility.phase !== "ready" || !name || profileSaveRef.current) return;
    setManagerName((draft) => draft === previousAuthoritativeName.current ? name : draft);
    previousAuthoritativeName.current = name;
  }, [eligibility.phase, eligibility.timing]);

  const saveProfile = async (nextName: string, nextAvatarUrl: string | null) => {
    if (!user || profileSaveRef.current) return;
    const input: { firstName?: string; avatarUrl?: string | null } = {};
    if (nextName !== (eligibility.timing?.current_name ?? user.firstName)) input.firstName = nextName;
    if (nextAvatarUrl !== (user.avatarUrl?.trim() || null)) input.avatarUrl = nextAvatarUrl;
    if (Object.keys(input).length === 0) return;
    const accountId = user.id;
    const controller = new AbortController(); profileSaveRef.current = controller;
    eligibility.invalidate();
    setSaveState("saving");
    setProfileError(null); setProfileErrorField(null);
    try {
      // Omit unchanged fields. Re-validating an unrelated legacy avatar used
      // to reject an otherwise eligible display-name update with HTTP 422.
      const updatedUser = await updateProfile(input, controller.signal);
      if (controller.signal.aborted || accountIdRef.current !== accountId) return;
      if (updatedUser.id !== accountId || updatedUser.firstName !== nextName) throw new Error("Your manager name was not changed. Please try again.");
      setManagerName(updatedUser.firstName); setAvatarUrl(updatedUser.avatarUrl ?? "");
      previousAuthoritativeName.current = updatedUser.firstName;
      setSaveState("saved");
      void eligibility.refresh();
      if (saveStateResetTimeoutRef.current) clearTimeout(saveStateResetTimeoutRef.current);
      saveStateResetTimeoutRef.current = setTimeout(() => { saveStateResetTimeoutRef.current = null; setSaveState("idle"); }, 1500);
    } catch (error) {
      if (controller.signal.aborted || accountIdRef.current !== accountId) return;
      showProfileError(error, "Unable to save your profile. Your previous settings are still active.", "first_name");
      setSaveState("error");
    } finally {
      if (profileSaveRef.current === controller) profileSaveRef.current = undefined;
    }
  };

  const handleSave = () => {
    if (!user || profileSaveRef.current || photoState === "saving") return;
    const nextName = managerName.trim();
    const nextAvatarUrl = avatarUrl.trim() || null;
    if (!nextName) {
      setProfileError("Manager name is required.");
      setProfileErrorField("first_name");
      setSaveState("error");
      return;
    }
    if (nextName.length > 50) {
      setProfileError("Manager name must be 50 characters or fewer.");
      setProfileErrorField("first_name");
      setSaveState("error");
      return;
    }
    setProfileError(null);
    setProfileErrorField(null);
    const isNameChange = nextName !== (eligibility.timing?.current_name ?? user.firstName);
    if (isNameChange && eligibility.phase !== "ready") {
      setProfileError("Name-change availability could not be confirmed. Retry the availability check before saving."); setProfileErrorField("first_name"); return;
    }
    if (isNameChange && managerNameCooldownActive) {
      setProfileError(`Need to wait until ${managerNameAvailableDateTime ?? "a later date"} before changing your manager name.`);
      setProfileErrorField("first_name");
      setSaveState("error");
      return;
    }
    if (isNameChange) {
      setPendingNameChange({ name: nextName, avatarUrl: nextAvatarUrl });
      return;
    }
    void saveProfile(nextName, nextAvatarUrl);
  };

  const handleReplayGuide = () => {
    if (!user) return;
    restartGuide(user.id);
    navigate("/", { state: { replayGuide: true } });
  };

  const handlePhotoChosen = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const accountId = user?.id;
    const photo = event.target.files?.[0];
    // Reset first so choosing the same image again emits a change event.
    event.target.value = "";
    if (!photo) return;

    setPhotoState("preparing");
    setProfileError(null);
    setProfileErrorField(null);
    setAvatarPreviewError(false);
    try {
      const preparedPhoto = await prepareProfileImage(photo);
      if (accountIdRef.current !== accountId) return;
      setPendingAvatarUrl(preparedPhoto);
      setPendingAvatarName(photo.name);
    } catch (error) {
      if (accountIdRef.current !== accountId) return;
      showProfileError(error, "Unable to prepare this photo.", "avatar_url");
    } finally {
      if (accountIdRef.current === accountId) setPhotoState("idle");
    }
  };

  const handleConfirmPhoto = async () => {
    if (!pendingAvatarUrl || !user || profileSaveRef.current) return;
    const accountId = user.id;
    const controller = new AbortController(); profileSaveRef.current = controller;
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
    setProfileErrorField(null);
    try {
      const updatedUser = await updateProfile({ avatarUrl: confirmedAvatarUrl }, controller.signal);
      if (controller.signal.aborted || accountIdRef.current !== accountId) return;
      setAvatarUrl(updatedUser.avatarUrl ?? confirmedAvatarUrl);
    } catch (error) {
      if (controller.signal.aborted || accountIdRef.current !== accountId) return;
      setAvatarUrl(previousAvatarUrl);
      showProfileError(error, "Unable to update your profile picture. Your previous picture is still active.", "avatar_url");
    } finally {
      if (profileSaveRef.current === controller) { profileSaveRef.current = undefined; setPhotoState("idle"); }
    }
  };

  const handleRemovePhoto = async () => {
    if (!user || profileSaveRef.current) return;
    const accountId = user.id;
    const controller = new AbortController(); profileSaveRef.current = controller;
    setPendingAvatarUrl(null);
    setPendingAvatarName(null);
    setAvatarPreviewError(false);
    setPhotoState("saving");
    setProfileError(null);
    setProfileErrorField(null);
    try {
      await updateProfile({ avatarUrl: null }, controller.signal);
      if (controller.signal.aborted || accountIdRef.current !== accountId) return;
      setAvatarUrl("");
    } catch (error) {
      if (controller.signal.aborted || accountIdRef.current !== accountId) return;
      showProfileError(error, "Unable to remove your profile picture. Your previous picture is still active.", "avatar_url");
    } finally {
      if (profileSaveRef.current === controller) { profileSaveRef.current = undefined; setPhotoState("idle"); }
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

  const handlePasswordResetEmail = async () => {
    if (!user || !passwordResetEnabled || !passwordResetEmailConfigured) return;
    const [local, domain] = user.email.split("@");
    const masked = `${local.slice(0, 1)}••••@${domain ?? ""}`;
    if (!window.confirm(`RESET YOUR PASSWORD?\n\nWe will email a secure reset link to ${masked}. Completing the reset signs you out on every device.`)) return;
    setIsSendingReset(true);
    setSecurityMessage(null);
    try {
      await requestPasswordResetForCurrentUser();
      setSecurityMessage("Reset email sent. The secure link expires in 30 minutes.");
    } catch (error) {
      setSecurityMessage(error instanceof ApiError && error.status === 429 ? "Too many reset requests. Please wait before trying again." : "Unable to send a reset email right now.");
    } finally {
      setIsSendingReset(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (accountDeletionConfirmation !== "DELETE") {
      setAccountDeletionError('Type DELETE exactly to confirm account deletion.');
      return;
    }
    if (!accountDeletionPassword) {
      setAccountDeletionError("Enter your current password to continue.");
      return;
    }
    setIsDeletingAccount(true);
    setAccountDeletionError(null);
    try {
      await deleteAccount(accountDeletionPassword, accountDeletionConfirmation);
      setAccountDeletionOpen(false);
      navigate("/login", { replace: true, state: { accountDeleted: true } });
    } catch (error) {
      setAccountDeletionError(error instanceof Error ? error.message : "Unable to delete your account right now.");
    } finally {
      setIsDeletingAccount(false);
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
    <>
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
            disabled={saveState === "saving" || photoState === "saving" || (managerName.trim() !== (eligibility.timing?.current_name ?? user.firstName) && eligibility.phase !== "ready")}
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
                maxLength={50}
                onChange={(event) => {
                  setManagerName(event.target.value);
                  if (profileErrorField === "first_name") {
                    setProfileError(null);
                    setProfileErrorField(null);
                  }
                }}
                onFocus={() => setIsManagerNameFocused(true)}
                onBlur={() => setIsManagerNameFocused(false)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    handleSave();
                  }
                }}
                disabled={managerNameCooldownActive}
                className="h-10 rounded-md border-border bg-background px-3 text-sm font-semibold text-foreground"
              />
              {isManagerNameFocused ? (
                <p aria-live="polite" className="text-[10px] font-black uppercase tracking-[0.12em] text-primary">
                  {managerName.length} / 50 characters
                </p>
              ) : null}
              {managerNameCooldownActive ? (
                <p className="text-xs font-medium text-muted-foreground" data-testid="name-change-wait">
                  You can change your name again in {formatNameChangeWait(eligibility.remainingSeconds)}.
                  <span className="block">Available: {managerNameAvailableDateTime}.</span>
                </p>
              ) : eligibility.phase === "checking" ? (
                <p className="text-xs font-medium text-muted-foreground">Checking name-change availability…</p>
              ) : eligibility.phase === "error" ? (
                <div className="text-xs font-medium text-muted-foreground">
                  <p>We couldn’t check name-change availability. Your name is unchanged.</p>
                  <Button type="button" variant="link" className="h-auto px-0 text-xs" onClick={() => void eligibility.refresh()}>Retry availability check</Button>
                </div>
              ) : (
                <p className="text-xs font-medium text-muted-foreground">You can change your manager name once every 7 days.</p>
              )}
              {profileError && profileErrorField === "first_name" ? (
                <div role="alert" className="relative rounded-md border border-red-400/35 bg-red-500/10 px-3 py-2 text-xs font-semibold leading-relaxed text-red-200 before:absolute before:-top-1.5 before:left-5 before:h-3 before:w-3 before:rotate-45 before:border-l before:border-t before:border-red-400/35 before:bg-red-500/10">
                  {profileError}
                </div>
              ) : null}
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
                    if (profileErrorField === "avatar_url") {
                      setProfileError(null);
                      setProfileErrorField(null);
                    }
                  }}
                  className="mt-3 h-10 rounded-md border-border bg-background px-3 text-sm text-foreground"
                />
              </details>
              {profileError && profileErrorField === "avatar_url" ? <p role="alert" className="text-xs font-semibold text-red-300">{profileError}</p> : null}
            </div>
          </div>
          {profileError && !profileErrorField ? <p role="alert" className="text-sm font-semibold text-red-300">{profileError}</p> : null}
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
            {passwordResetEnabled && passwordResetEmailConfigured ? <div className="rounded-lg border border-primary/25 bg-primary/5 p-4"><h3 className="text-sm font-black uppercase tracking-[0.16em] text-foreground">Password reset by email</h3><p className="mt-2 text-sm font-medium text-muted-foreground">We’ll send a secure reset link to your account email. Completing the reset signs you out on every device.</p><Button type="button" className="mt-4 h-11 rounded-xl text-[10px] font-black uppercase tracking-widest" onClick={() => void handlePasswordResetEmail()} disabled={isSendingReset}>{isSendingReset ? "Sending…" : "Reset password by email"}</Button></div> : null}
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
            <div className="rounded-lg border border-red-500/35 bg-red-500/5 p-4">
              {import.meta.env.VITE_MEMBERSHIP_ENABLED === "true" && <div className="mb-6 space-y-2"><h3 className="cfb-section-title">CFFB Pro membership</h3><p>$10 USD/year from the 2027 season: unlimited leagues, faster scoring refresh, player pictures, dynasty and weekly challenges.</p><Button asChild variant="outline"><Link to="/membership">View or manage membership</Link></Button><p className="text-sm">Web renewal is cancelled when you delete your account. App Store subscriptions must be managed with Apple.</p></div>}
              <h3 className="text-sm font-black uppercase tracking-[0.16em] text-red-200">Delete Account</h3>
              <p className="mt-2 text-sm font-medium leading-relaxed text-muted-foreground">
                Permanently delete your account, profile, sign-in sessions, saved preferences, and personal content. League history remains anonymized for other managers. This cannot be undone.
              </p>
              <Button
                type="button"
                variant="outline"
                className="mt-4 h-11 border-red-400/60 bg-transparent text-[10px] font-black uppercase tracking-widest text-red-200 hover:bg-red-500/10 hover:text-red-100"
                onClick={() => {
                  setAccountDeletionError(null);
                  setAccountDeletionPassword("");
                  setAccountDeletionConfirmation("");
                  setAccountDeletionOpen(true);
                }}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete My Account
              </Button>
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
      <AlertDialog
        open={pendingNameChange !== null}
        onOpenChange={(open) => {
          if (!open) setPendingNameChange(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Change manager name?</AlertDialogTitle>
            <AlertDialogDescription>
              This updates your manager identity across league pages, including matchups. You can only change it once every 7 days.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep current name</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const change = pendingNameChange;
                setPendingNameChange(null);
                if (change) void saveProfile(change.name, change.avatarUrl);
              }}
            >
              Confirm name change
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={accountDeletionOpen} onOpenChange={setAccountDeletionOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete your account permanently?</AlertDialogTitle>
            <AlertDialogDescription>
              This erases your account and personal data. Your league history will remain only as anonymized records for other managers.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="account-deletion-password">Current password</Label>
              <Input
                id="account-deletion-password"
                type="password"
                autoComplete="current-password"
                value={accountDeletionPassword}
                onChange={(event) => setAccountDeletionPassword(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-deletion-confirmation">Type DELETE to confirm</Label>
              <Input
                id="account-deletion-confirmation"
                value={accountDeletionConfirmation}
                onChange={(event) => setAccountDeletionConfirmation(event.target.value)}
                autoComplete="off"
              />
            </div>
            {accountDeletionError ? <p role="alert" className="text-sm font-semibold text-red-300">{accountDeletionError}</p> : null}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletingAccount}>Keep My Account</AlertDialogCancel>
            <Button
              type="button"
              variant="destructive"
              onClick={() => void handleDeleteAccount()}
              disabled={isDeletingAccount}
            >
              {isDeletingAccount ? "Deleting…" : "Delete Account Permanently"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
