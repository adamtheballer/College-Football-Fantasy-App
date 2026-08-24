import { FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, Eye, EyeOff, KeyRound, Loader2, ShieldAlert, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SurfaceCard } from "@/components/fantasy";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { PASSWORD_POLICY_MESSAGE, passwordMeetsPolicy, passwordPolicyChecks } from "@/lib/password-policy";

const passwordError = (password: string, confirm: string) => {
  if (!passwordMeetsPolicy(password)) return PASSWORD_POLICY_MESSAGE;
  if (password !== confirm) return "Passwords do not match.";
  return null;
};

export default function ResetPassword() {
  const location = useLocation();
  const navigate = useNavigate();
  const { validatePasswordReset, confirmPasswordReset } = useAuth();
  const [token] = useState(() => new URLSearchParams(location.search).get("token") ?? "");
  const [validity, setValidity] = useState<"checking" | "valid" | "invalid">("checking");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const policyChecks = passwordPolicyChecks(password);
  const confirmationCheck = { label: "Passwords match", isValid: Boolean(confirm) && password === confirm };
  const canSubmit = !submitting && passwordMeetsPolicy(password) && confirmationCheck.isValid;

  useEffect(() => {
    window.history.replaceState(null, "", "/reset-password");
    if (!token) { setValidity("invalid"); return; }
    void validatePasswordReset(token).then((valid) => setValidity(valid ? "valid" : "invalid")).catch(() => setValidity("invalid"));
  }, [token, validatePasswordReset]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const validation = passwordError(password, confirm);
    if (validation) { setError(validation); return; }
    setSubmitting(true); setError(null);
    try {
      await confirmPasswordReset(token, password, confirm);
      setPassword(""); setConfirm(""); setSuccess(true);
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 400 ? "This reset link is invalid or expired." : "Unable to reset your password right now. Please retry.");
    } finally { setSubmitting(false); }
  };

  const field = (id: string, label: string, value: string, setValue: (value: string) => void, shown: boolean, setShown: (value: boolean) => void) => <div className="block text-[10px] font-black uppercase tracking-widest text-cfb-text-muted"><label htmlFor={id}>{label}</label><span className="relative mt-2 block"><Input id={id} type={shown ? "text" : "password"} autoComplete="new-password" value={value} onChange={(event) => { setValue(event.target.value); setError(null); }} className="h-14 rounded-2xl pr-12 text-base" required /><button type="button" aria-label={shown ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`} onClick={() => setShown(!shown)} className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-cfb-text-muted">{shown ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></span></div>;

  return <main className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-xl items-center px-4 py-8 sm:px-6"><SurfaceCard variant="raised" padding="spacious" className="w-full"><div className="text-center"><KeyRound className="mx-auto h-10 w-10 text-cfb-cyan" aria-hidden="true" /><p className="cfb-micro-label mt-4 text-cfb-brand">Account recovery</p><h1 className="mt-2 text-3xl font-black uppercase italic text-cfb-text-primary">{success ? "Password updated" : "Reset password"}</h1></div>{success ? <div className="mt-8 rounded-2xl border border-cfb-success/30 bg-cfb-success/10 p-5 text-center text-sm font-semibold text-emerald-50"><CheckCircle2 className="mx-auto h-8 w-8" /><p className="mt-3">Your password has been changed. You have been signed out on all devices.</p><Button className="mt-5" onClick={() => navigate("/login")}>Return to sign in</Button></div> : validity === "checking" ? <p role="status" className="mt-8 flex justify-center gap-2 text-sm text-cfb-text-secondary"><Loader2 className="h-4 w-4 animate-spin" />Validating reset link…</p> : validity === "invalid" ? <div className="mt-8 text-center"><ShieldAlert className="mx-auto h-8 w-8 text-red-300" /><h2 className="mt-3 text-lg font-black uppercase text-cfb-text-primary">This reset link is invalid or expired</h2><p className="mt-2 text-sm text-cfb-text-secondary">Request a new reset email to continue.</p><Link to="/forgot-password" className="mt-5 inline-block text-xs font-black uppercase tracking-widest text-cfb-cyan">Request new link</Link></div> : <form className="mt-8 space-y-5" onSubmit={submit}>{field("new-password", "New password", password, setPassword, showPassword, setShowPassword)}<div className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/55 p-4" aria-live="polite"><p className="text-xs font-semibold text-cfb-text-secondary">{PASSWORD_POLICY_MESSAGE}</p><ul className="mt-3 grid gap-2 sm:grid-cols-2" aria-label="Password requirements">{[...policyChecks, confirmationCheck].map((check) => <li key={check.label} data-valid={check.isValid ? "true" : "false"} className={`flex items-center gap-2 text-[10px] font-black uppercase tracking-wider ${check.isValid ? "text-cfb-success" : "text-cfb-danger"}`}>{check.isValid ? <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" /> : <XCircle className="h-4 w-4 shrink-0" aria-hidden="true" />}<span>{check.label}</span><span className="sr-only">{check.isValid ? " met" : " not met"}</span></li>)}</ul></div>{field("confirm-password", "Confirm new password", confirm, setConfirm, showConfirm, setShowConfirm)}{error ? <p role="alert" className="text-sm font-semibold text-red-200">{error}</p> : null}<Button type="submit" className="h-14 w-full rounded-2xl" disabled={!canSubmit}>{submitting ? "Creating password…" : "Create new password"}</Button></form>} {!success ? <Link to="/login" className="mt-6 block text-center text-xs font-black uppercase tracking-widest text-cfb-cyan">Back to sign in</Link> : null}</SurfaceCard></main>;
}
