import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { KeyRound, LockKeyhole, Mail, ShieldCheck, Trophy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiUnavailableMessage } from "@/lib/api";
import { validateBetaAccess } from "@/lib/beta-access";

export default function BetaAccess() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const reservation = await validateBetaAccess(email, code);
      navigate(reservation.existingAccount ? "/login" : "/signup", {
        replace: true,
        state: reservation.existingAccount ? { betaAccessPending: true } : undefined,
      });
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 0) {
        setError(apiUnavailableMessage());
      } else if (caught instanceof Error) {
        setError(caught.message);
      } else {
        setError("Unable to verify early access. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="relative mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-3xl items-center justify-center overflow-hidden px-4 py-10">
      <div aria-hidden="true" className="pointer-events-none absolute -left-28 top-12 h-72 w-72 rounded-full bg-cyan-300/15 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-24 bottom-6 h-80 w-80 rounded-full bg-violet-500/15 blur-3xl" />
      <section className="relative w-full overflow-hidden rounded-[2rem] border border-sky-300/30 bg-slate-950/90 shadow-[0_0_80px_rgba(56,189,248,0.15)]">
        <div className="h-1.5 bg-gradient-to-r from-cyan-300 via-sky-500 to-violet-500" />
        <div className="space-y-7 p-7 sm:p-10">
          <div className="space-y-4 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-200/35 bg-cyan-300/10 text-cyan-100 shadow-[0_0_32px_rgba(34,211,238,0.22)]">
              <Trophy className="h-8 w-8" aria-hidden="true" />
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-cyan-200">College Football Fantasy</p>
              <h1 className="mt-3 text-4xl font-black uppercase italic tracking-tight text-white sm:text-5xl">Early Access</h1>
              <p className="mx-auto mt-3 max-w-lg text-sm font-medium leading-6 text-slate-300">
                Enter the email address and early-access code you received to create your beta account.
              </p>
            </div>
          </div>

          <form className="space-y-4" onSubmit={submit}>
            <label className="block space-y-2">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-300">Email address</span>
              <span className="relative block">
                <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-200/70" aria-hidden="true" />
                <Input
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="h-13 rounded-2xl border-white/15 bg-slate-900/75 pl-11 text-base font-bold text-white"
                  required
                />
              </span>
            </label>
            <label className="block space-y-2">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-300">Early-access code</span>
              <span className="relative block">
                <KeyRound className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-200/70" aria-hidden="true" />
                <Input
                  value={code}
                  onChange={(event) => setCode(event.target.value.toUpperCase())}
                  className="h-13 rounded-2xl border-white/15 bg-slate-900/75 pl-11 text-base font-bold uppercase tracking-[0.16em] text-white"
                  placeholder="EARLY-XXXXXX"
                  autoCapitalize="characters"
                  required
                />
              </span>
            </label>
            {error ? (
              <p role="alert" className="rounded-2xl border border-rose-300/30 bg-rose-500/15 px-4 py-3 text-sm font-bold text-rose-100">
                {error}
              </p>
            ) : null}
            <Button className="h-14 w-full rounded-2xl bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-[11px] font-black uppercase tracking-[0.22em] text-slate-950" disabled={isSubmitting}>
              {isSubmitting ? "Verifying access..." : "Continue"}
            </Button>
          </form>

          <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-center">
            <p className="flex items-center justify-center gap-2 text-xs font-semibold text-slate-300"><LockKeyhole className="h-4 w-4 text-cyan-200" /> Your code is validated securely and never displayed again.</p>
            <p className="text-xs text-slate-400">Use the same email address where you received your code.</p>
            <p className="text-xs text-slate-400">Sign in if you already created your account and entered your code.</p>
            <Link to="/login" className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-cyan-200 hover:text-cyan-100">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" /> Sign in
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
