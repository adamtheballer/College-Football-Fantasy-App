import { useMemo, useState } from "react";
import { Eye, EyeOff, Lock, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import {
  PASSWORD_POLICY_MESSAGE,
  passwordPolicyChecks,
  validatePasswordChange,
} from "@/lib/password-policy";

type PasswordChangeFormProps = {
  mode: "reset" | "authenticated";
  onCancel?: () => void;
  onSuccess: () => void;
};

const credentialFailureMessage = "Unable to reset password with the provided credentials.";

export function PasswordChangeForm({ mode, onCancel, onSuccess }: PasswordChangeFormProps) {
  const { changePassword, resetPasswordWithCurrentPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [showPasswords, setShowPasswords] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validationError = useMemo(
    () => validatePasswordChange(currentPassword, newPassword, confirmNewPassword),
    [confirmNewPassword, currentPassword, newPassword],
  );
  const canSubmit =
    !isSubmitting &&
    !validationError &&
    (mode === "authenticated" || email.trim().length > 0);

  const clearPasswords = () => {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmNewPassword("");
    setShowPasswords(false);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;

    setError(null);
    setIsSubmitting(true);
    try {
      if (mode === "authenticated") {
        await changePassword(currentPassword, newPassword, confirmNewPassword);
      } else {
        await resetPasswordWithCurrentPassword(email, currentPassword, newPassword, confirmNewPassword);
      }
      clearPasswords();
      onSuccess();
    } catch (requestError) {
      clearPasswords();
      if (requestError instanceof ApiError && requestError.status === 400) {
        setError(credentialFailureMessage);
      } else if (requestError instanceof ApiError && requestError.status === 422) {
        setError(requestError.message);
      } else if (requestError instanceof ApiError && requestError.status === 429) {
        setError("Too many password reset attempts. Wait a few minutes and try again.");
      } else {
        setError("Unable to reset password right now. Try again later.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const passwordType = showPasswords ? "text" : "password";
  const policyChecks = passwordPolicyChecks(newPassword);

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {mode === "reset" ? (
        <label className="grid gap-2">
          <span className="text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">Email address</span>
          <span className="group relative block">
            <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted" aria-hidden="true" />
            <Input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="h-12 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-11"
              required
            />
          </span>
        </label>
      ) : null}

      {[
        ["Current password", currentPassword, setCurrentPassword, "current-password"],
        ["New password", newPassword, setNewPassword, "new-password"],
        ["Confirm new password", confirmNewPassword, setConfirmNewPassword, "new-password"],
      ].map(([label, value, setValue, autoComplete]) => (
        <label key={label as string} className="grid gap-2">
          <span className="text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">{label as string}</span>
          <span className="group relative block">
            <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted" aria-hidden="true" />
            <Input
              type={passwordType}
              autoComplete={autoComplete as string}
              value={value as string}
              onChange={(event) => (setValue as (nextValue: string) => void)(event.target.value)}
              className="h-12 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-11 pr-12"
              required
            />
            <button
              type="button"
              aria-label={showPasswords ? "Hide passwords" : "Show passwords"}
              onClick={() => setShowPasswords((visible) => !visible)}
              className="absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-cfb-text-muted hover:bg-white/10 hover:text-cfb-text-primary"
            >
              {showPasswords ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </span>
        </label>
      ))}

      <div className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/55 p-4" aria-live="polite">
        <p className="text-xs font-semibold text-cfb-text-secondary">{PASSWORD_POLICY_MESSAGE}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {policyChecks.map((check) => (
            <span
              key={check.label}
              className={`text-[10px] font-black uppercase tracking-wider ${check.isValid ? "text-cfb-success" : "text-cfb-text-muted"}`}
            >
              {check.label}
            </span>
          ))}
        </div>
        {newPassword && confirmNewPassword && newPassword !== confirmNewPassword ? (
          <p className="mt-3 text-xs font-bold text-cfb-danger">New passwords do not match.</p>
        ) : null}
      </div>

      {error ? <p role="alert" className="rounded-2xl border border-cfb-danger/35 bg-cfb-danger/[0.14] px-4 py-3 text-sm font-bold text-red-100">{error}</p> : null}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        {onCancel ? <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button> : null}
        <Button type="submit" disabled={!canSubmit} className="bg-gradient-to-r from-cfb-cyan to-cfb-brand text-slate-950">
          {isSubmitting ? "Resetting password..." : "Reset Password"}
        </Button>
      </div>
    </form>
  );
}
