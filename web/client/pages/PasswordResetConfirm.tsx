import React, { useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, Lock, ShieldCheck, Trophy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";

const passwordPolicyMessage =
  "Password must be at least 12 characters and include one uppercase letter, one number, and one special character.";

export default function PasswordResetConfirm() {
  const { confirmPasswordReset } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const token = useMemo(() => new URLSearchParams(location.search).get("token") || "", [location.search]);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(token ? null : "Reset token is missing. Request a new reset link.");

  const passwordChecks = [
    { label: "12+ characters", isValid: password.length >= 12 },
    { label: "One uppercase letter", isValid: /[A-Z]/.test(password) },
    { label: "One number", isValid: /\d/.test(password) },
    { label: "One special character", isValid: /[^A-Za-z0-9]/.test(password) },
  ];
  const isPasswordStrong = passwordChecks.every((check) => check.isValid);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token) {
      setError("Reset token is missing. Request a new reset link.");
      return;
    }
    if (!isPasswordStrong) {
      setError(passwordPolicyMessage);
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      navigate("/login", {
        replace: true,
        state: { notice: "Password reset complete. Sign in with your new password." },
      });
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setError(detail || "Reset link is invalid or expired. Request a new link.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative flex h-full max-h-full items-center justify-center overflow-hidden rounded-[2rem] border border-white/10 bg-[#06111f] p-4 shadow-[0_0_80px_rgba(14,165,233,0.18)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(34,211,238,0.34),transparent_34%),radial-gradient(circle_at_84%_18%,rgba(251,191,36,0.24),transparent_28%),linear-gradient(135deg,rgba(15,23,42,0.15),rgba(2,6,23,0.88))]" />
      <div className="absolute inset-0 opacity-[0.16] [background-image:linear-gradient(rgba(255,255,255,0.16)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.16)_1px,transparent_1px)] [background-size:48px_48px]" />

      <Card className="relative w-full max-w-[500px] overflow-hidden rounded-[1.75rem] border border-white/15 bg-slate-950/78 shadow-[0_28px_80px_rgba(0,0,0,0.42)] backdrop-blur-2xl">
        <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-cyan-300 via-amber-200 to-rose-400" />
        <CardContent className="relative space-y-5 p-6 sm:p-8">
          <div className="space-y-3 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-200 via-cyan-300 to-blue-500 shadow-[0_0_38px_rgba(34,211,238,0.34)]">
              <Trophy className="h-6 w-6 text-slate-950" />
            </div>
            <div>
              <h1 className="text-3xl font-black uppercase italic tracking-tight text-white">Create New Password</h1>
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100/60">
                This will revoke old sessions and store a new secure password hash.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="ml-3 text-[10px] font-black uppercase tracking-widest text-cyan-100/70">New Password</label>
              <div className="group relative">
                <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  className="h-12 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 pr-12 text-sm font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((current) => !current)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full p-1 text-cyan-100/45 transition-colors hover:text-cyan-100 focus:outline-none focus:ring-2 focus:ring-cyan-300/30"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
              <div className="grid gap-2 sm:grid-cols-2">
                {passwordChecks.map((check) => (
                  <div key={check.label} className={`flex items-center gap-2 text-[9px] font-black uppercase tracking-[0.14em] ${check.isValid ? "text-emerald-200" : "text-slate-300/45"}`}>
                    <span className={`h-2 w-2 rounded-full ${check.isValid ? "bg-emerald-300" : "bg-slate-400/35"}`} />
                    {check.label}
                  </div>
                ))}
              </div>
            </div>

            {error && (
              <div className="rounded-2xl border border-red-300/35 bg-red-500/15 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-red-100">
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="h-12 w-full rounded-2xl bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-[10px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_18px_42px_rgba(14,165,233,0.32)] transition-all hover:brightness-110"
              disabled={isSubmitting || !token}
            >
              {isSubmitting ? "Saving..." : "Save New Password"}
            </Button>
          </form>

          <div className="flex items-center justify-between border-t border-white/10 pt-4 text-[10px] font-black uppercase tracking-widest text-slate-300/70">
            <Link to="/password-reset" className="inline-flex items-center gap-2 text-cyan-100/75 hover:text-cyan-100">
              <ArrowLeft className="h-3.5 w-3.5" />
              Request New Link
            </Link>
            <span className="inline-flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-200" />
              Argon2 Protected
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
