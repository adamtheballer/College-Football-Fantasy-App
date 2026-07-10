import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Mail, RefreshCw, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";

type VerificationState = "missing-token" | "verifying" | "verified" | "failed";

export const verificationErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.status === 400) {
      return "This verification link is invalid or expired. Request a new verification email below.";
    }
    if (error.status === 0) {
      return "Unable to reach the backend API. Start FastAPI and try again.";
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unable to verify this email address.";
};

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";
  const { user, verifyEmail, resendVerification } = useAuth();
  const [state, setState] = useState<VerificationState>(token ? "verifying" : "missing-token");
  const [message, setMessage] = useState<string | null>(null);
  const [email, setEmail] = useState(user?.email ?? "");
  const [isResending, setIsResending] = useState(false);
  const [resendNotice, setResendNotice] = useState<string | null>(null);

  const title = useMemo(() => {
    if (state === "verified") return "Email Verified";
    if (state === "verifying") return "Verifying Email";
    return "Verify Your Email";
  }, [state]);

  useEffect(() => {
    setEmail((current) => current || user?.email || "");
  }, [user?.email]);

  useEffect(() => {
    if (!token) {
      setState("missing-token");
      setMessage("The verification link is missing a token.");
      return;
    }

    let cancelled = false;
    setState("verifying");
    setMessage(null);
    verifyEmail(token)
      .then(() => {
        if (cancelled) return;
        setState("verified");
        setMessage("Your account email is verified. You can now create and join leagues.");
      })
      .catch((error) => {
        if (cancelled) return;
        setState("failed");
        setMessage(verificationErrorMessage(error));
      });

    return () => {
      cancelled = true;
    };
  }, [token, verifyEmail]);

  const handleResend = async (event: FormEvent) => {
    event.preventDefault();
    setResendNotice(null);
    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setResendNotice("Enter the email address for the account you need to verify.");
      return;
    }
    setIsResending(true);
    try {
      await resendVerification(normalizedEmail);
      setResendNotice("If that account still needs verification, a new email was sent.");
    } catch (error) {
      setResendNotice(error instanceof Error ? error.message : "Unable to resend verification email.");
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-3xl items-center justify-center py-12">
      <Card className="w-full overflow-hidden rounded-[2.25rem] border border-white/10 bg-slate-950/80 shadow-[0_0_80px_rgba(14,165,233,0.18)]">
        <div className="h-1.5 bg-gradient-to-r from-cyan-300 via-amber-200 to-emerald-300" />
        <CardContent className="space-y-8 p-8 text-center sm:p-10">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-200/20 bg-cyan-300/10">
            {state === "verified" ? (
              <CheckCircle2 className="h-8 w-8 text-emerald-200" />
            ) : state === "verifying" ? (
              <RefreshCw className="h-8 w-8 animate-spin text-cyan-200" />
            ) : (
              <AlertTriangle className="h-8 w-8 text-amber-200" />
            )}
          </div>

          <div className="space-y-3">
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-100/70">
              Account Security
            </p>
            <h1 className="text-4xl font-black uppercase italic tracking-tight text-white sm:text-5xl">
              {title}
            </h1>
            <p className="mx-auto max-w-xl text-sm font-bold leading-6 text-slate-300">
              {message ??
                "Checking your verification link. This should only take a few seconds."}
            </p>
          </div>

          {state === "verified" ? (
            <div className="flex flex-col justify-center gap-3 sm:flex-row">
              <Button asChild className="h-12 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]">
                <Link to="/">Go To Dashboard</Link>
              </Button>
              <Button asChild variant="outline" className="h-12 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]">
                <Link to="/leagues/create">Create League</Link>
              </Button>
            </div>
          ) : (
            <form onSubmit={handleResend} className="mx-auto max-w-xl space-y-4 rounded-2xl border border-white/10 bg-white/[0.04] p-5 text-left">
              <div className="space-y-2">
                <label className="ml-2 text-[10px] font-black uppercase tracking-[0.2em] text-cyan-100/70">
                  Resend Verification Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45" />
                  <Input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="coach@saturday.com"
                    className="h-12 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-sm font-bold text-white placeholder:text-slate-300/40"
                  />
                </div>
              </div>
              {resendNotice ? (
                <p className="rounded-2xl border border-cyan-200/20 bg-cyan-300/10 px-4 py-3 text-[10px] font-black uppercase tracking-[0.14em] text-cyan-100">
                  {resendNotice}
                </p>
              ) : null}
              <Button
                type="submit"
                disabled={isResending}
                className="h-12 w-full rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              >
                {isResending ? "Sending..." : "Resend Verification"}
              </Button>
            </form>
          )}

          <div className="flex flex-col items-center justify-center gap-3 border-t border-white/10 pt-6 text-[10px] font-black uppercase tracking-[0.16em] text-slate-300/70 sm:flex-row">
            <span className="inline-flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-200" />
              Verified accounts unlock league actions
            </span>
            <Link to="/login" className="text-amber-200 hover:text-amber-100">
              Back to sign in
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
