import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowLeft, Mail, ShieldCheck, Trophy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiPost } from "@/lib/api";

type VerificationStatus = "idle" | "verifying" | "success" | "error";

type AuthMessageResponse = {
  success?: boolean;
  message?: string;
};

export const getVerifyEmailToken = (search: string) =>
  new URLSearchParams(search).get("token")?.trim() ?? "";

export const verifyEmailTokenRequest = (token: string) =>
  apiPost<AuthMessageResponse>("/auth/verify-email", { token });

export const resendVerificationRequest = (email: string) =>
  apiPost<AuthMessageResponse>("/auth/resend-verification", { email });

const readErrorMessage = (error: unknown, fallback: string) =>
  error instanceof Error && error.message ? error.message : fallback;

export default function VerifyEmail() {
  const location = useLocation();
  const token = useMemo(() => getVerifyEmailToken(location.search), [location.search]);
  const [status, setStatus] = useState<VerificationStatus>(token ? "idle" : "error");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(
    token ? null : "Verification token is missing. Request a new verification email."
  );
  const [email, setEmail] = useState("");
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const [resendError, setResendError] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);

  useEffect(() => {
    if (!token) return;

    let isCurrent = true;
    setStatus("verifying");
    setError(null);
    setMessage(null);

    verifyEmailTokenRequest(token)
      .then((payload) => {
        if (!isCurrent) return;
        setStatus("success");
        setMessage(payload.message || "Email verified. You can now sign in and use every league feature.");
      })
      .catch((verifyError) => {
        if (!isCurrent) return;
        setStatus("error");
        setError(readErrorMessage(verifyError, "Verification link is invalid or expired. Request a new email."));
      });

    return () => {
      isCurrent = false;
    };
  }, [token]);

  const handleResend = async (event: React.FormEvent) => {
    event.preventDefault();
    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setResendError("Enter the email address you used to sign up.");
      return;
    }

    setIsResending(true);
    setResendMessage(null);
    setResendError(null);
    try {
      const payload = await resendVerificationRequest(normalizedEmail);
      setResendMessage(payload.message || "If this account needs verification, a new email was sent.");
    } catch (resendFailure) {
      setResendError(readErrorMessage(resendFailure, "Could not resend verification. Try again."));
    } finally {
      setIsResending(false);
    }
  };

  const statusTitle =
    status === "success"
      ? "Email Verified"
      : status === "verifying"
        ? "Verifying Email"
        : "Verification Link Needs Attention";

  const statusCopy =
    status === "success"
      ? message
      : status === "verifying"
        ? "Checking this verification link with the secure auth service."
        : error;

  return (
    <div className="relative flex h-full max-h-full items-center justify-center overflow-hidden rounded-[2rem] border border-white/10 bg-[#06111f] p-4 shadow-[0_0_80px_rgba(14,165,233,0.18)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(34,211,238,0.34),transparent_34%),radial-gradient(circle_at_84%_18%,rgba(251,191,36,0.24),transparent_28%),linear-gradient(135deg,rgba(15,23,42,0.15),rgba(2,6,23,0.88))]" />
      <div className="absolute inset-0 opacity-[0.16] [background-image:linear-gradient(rgba(255,255,255,0.16)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.16)_1px,transparent_1px)] [background-size:48px_48px]" />

      <Card className="relative w-full max-w-[520px] overflow-hidden rounded-[1.75rem] border border-white/15 bg-slate-950/78 shadow-[0_28px_80px_rgba(0,0,0,0.42)] backdrop-blur-2xl">
        <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-cyan-300 via-amber-200 to-rose-400" />
        <CardContent className="relative space-y-6 p-6 sm:p-8">
          <div className="space-y-3 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-200 via-cyan-300 to-blue-500 shadow-[0_0_38px_rgba(34,211,238,0.34)]">
              <Trophy className="h-6 w-6 text-slate-950" />
            </div>
            <div>
              <h1 className="text-3xl font-black uppercase italic tracking-tight text-white">{statusTitle}</h1>
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100/60">
                Public account verification
              </p>
            </div>
          </div>

          <div
            className={`rounded-2xl border px-4 py-4 text-sm font-bold leading-6 ${
              status === "success"
                ? "border-emerald-200/35 bg-emerald-300/12 text-emerald-100"
                : status === "verifying"
                  ? "border-cyan-200/25 bg-cyan-300/10 text-cyan-100"
                  : "border-red-300/35 bg-red-500/15 text-red-100"
            }`}
          >
            {statusCopy}
          </div>

          {status === "error" ? (
            <form onSubmit={handleResend} className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.06] p-4">
              <div className="space-y-2">
                <label className="ml-3 text-[10px] font-black uppercase tracking-widest text-cyan-100/70">
                  Resend Verification Email
                </label>
                <div className="group relative">
                  <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                  <Input
                    type="email"
                    placeholder="coach@saturday.com"
                    className="h-12 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-sm font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25"
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value);
                      setResendError(null);
                      setResendMessage(null);
                    }}
                    required
                  />
                </div>
              </div>

              {resendMessage ? (
                <div className="rounded-2xl border border-emerald-200/35 bg-emerald-300/12 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-100">
                  {resendMessage}
                </div>
              ) : null}
              {resendError ? (
                <div className="rounded-2xl border border-red-300/35 bg-red-500/15 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-red-100">
                  {resendError}
                </div>
              ) : null}

              <Button
                type="submit"
                className="h-12 w-full rounded-2xl bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-[10px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_18px_42px_rgba(14,165,233,0.32)] transition-all hover:brightness-110"
                disabled={isResending}
              >
                {isResending ? "Sending..." : "Send New Verification Email"}
              </Button>
            </form>
          ) : null}

          <div className="flex items-center justify-between border-t border-white/10 pt-4 text-[10px] font-black uppercase tracking-widest text-slate-300/70">
            <Link to="/login" className="inline-flex items-center gap-2 text-cyan-100/75 hover:text-cyan-100">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Sign In
            </Link>
            <span className="inline-flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-200" />
              Account Security
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
