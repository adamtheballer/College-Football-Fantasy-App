import { FormEvent, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, KeyRound, Loader2, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiUnavailableMessage } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

export const passwordResetErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.status === 400) return "This password reset link is invalid, expired, or already used.";
    if (error.status === 429) return "Too many reset attempts. Wait a few minutes and try again.";
    if (error.status === 0) return `Unable to reach the backend API. ${apiUnavailableMessage()}`;
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Unable to reset password.";
};

export const validateNewPassword = (password: string, confirmation: string) => {
  if (password.length < 12) return "Password must be at least 12 characters.";
  if (!/[A-Z]/.test(password)) return "Password must include an uppercase letter.";
  if (!/\d/.test(password)) return "Password must include a number.";
  if (!/[^A-Za-z0-9]/.test(password)) return "Password must include a special character.";
  if (password !== confirmation) return "Passwords do not match.";
  return null;
};

export default function PasswordResetConfirm() {
  const location = useLocation();
  const navigate = useNavigate();
  const { confirmPasswordReset } = useAuth();
  const token = useMemo(() => new URLSearchParams(location.search).get("token") ?? "", [location.search]);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(token ? null : "This password reset link is missing a token.");
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const validationError = validateNewPassword(password, confirmation);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (!token) {
      setError("This password reset link is missing a token.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      window.history.replaceState(null, "", "/password-reset/confirm");
      setSuccess(true);
    } catch (err) {
      setError(passwordResetErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-3xl items-center px-6 py-10">
      <section className="w-full rounded-[2rem] border border-sky-300/20 bg-slate-950/70 p-8 shadow-[0_0_60px_rgba(56,189,248,0.16)]">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-300/15 text-sky-100">
            {success ? <CheckCircle2 className="h-7 w-7" /> : <KeyRound className="h-7 w-7" />}
          </div>
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.24em] text-sky-300">Account Recovery</p>
            <h1 className="mt-1 text-3xl font-black italic text-slate-50">
              {success ? "Password Reset Complete" : "Set a New Password"}
            </h1>
          </div>
        </div>

        {success ? (
          <div className="mt-8 rounded-3xl border border-emerald-300/20 bg-emerald-400/10 p-6">
            <p className="text-sm font-bold text-emerald-50">
              Your password has been updated. Sign in with the new password to continue.
            </p>
            <Button type="button" className="mt-5" onClick={() => navigate("/login")}>
              Back to Login
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-8 space-y-5">
            <div>
              <label className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400" htmlFor="new-password">
                New Password
              </label>
              <Input
                id="new-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 h-13 rounded-2xl"
                required
              />
            </div>
            <div>
              <label className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400" htmlFor="confirm-password">
                Confirm Password
              </label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                className="mt-2 h-13 rounded-2xl"
                required
              />
            </div>
            {error ? (
              <div className="flex gap-3 rounded-2xl border border-red-300/20 bg-red-500/10 p-4 text-sm font-bold text-red-100">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </div>
            ) : null}
            <Button type="submit" className="w-full" disabled={isSubmitting || !token}>
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Reset Password
            </Button>
            <Link to="/login" className="block text-center text-xs font-black uppercase tracking-[0.18em] text-sky-200 hover:text-sky-100">
              Back to Login
            </Link>
          </form>
        )}
      </section>
    </main>
  );
}
