import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CalendarClock,
  Eye,
  EyeOff,
  Lock,
  Mail,
  ShieldCheck,
  Trophy,
  Users,
  Zap,
} from "lucide-react";

import { PlaybookDecor, SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { ApiError, apiUnavailableMessage } from "@/lib/api";
import { setPendingGuide } from "@/lib/onboarding";

const featureCards = [
  {
    title: "Draft board",
    body: "Enter league drafts and mock draft rooms from the same product shell.",
    icon: Trophy,
    tone: "text-cfb-gold border-cfb-gold/30 bg-cfb-gold/[0.08]",
  },
  {
    title: "Roster control",
    body: "Review lineups, locks, alerts, and roster status before kickoff.",
    icon: ShieldCheck,
    tone: "text-cfb-success border-cfb-success/30 bg-cfb-success/[0.08]",
  },
  {
    title: "League hub",
    body: "Manage standings, members, settings, watchlists, and matchup context.",
    icon: Users,
    tone: "text-cfb-cyan border-cfb-cyan/30 bg-cfb-cyan/[0.08]",
  },
] as const;

export const loginErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return apiUnavailableMessage();
    }
    if (error.status === 401) {
      return "Email or password is incorrect.";
    }
    if (error.status === 423) {
      return "This account is temporarily locked after too many failed attempts. Try again later or reset your password.";
    }
    if (error.status === 429) {
      return "Too many sign-in attempts. Wait a few minutes and try again.";
    }
    if (error.status === 422) {
      return error.message;
    }
    if (error.status >= 500) {
      return "The sign-in service hit an error. Try again or contact support.";
    }
  }

  if (error instanceof Error && error.message.includes("Failed to fetch")) {
    return apiUnavailableMessage();
  }

  return "Sign in failed. Try again or contact support.";
};

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoggedIn } = useAuth();
  const redirectTarget =
    typeof location.state === "object" &&
    location.state &&
    "from" in location.state &&
    typeof location.state.from === "string"
      ? location.state.from
      : "/";

  useEffect(() => {
    if (isLoggedIn) {
      navigate(redirectTarget, { replace: true });
    }
  }, [isLoggedIn, navigate, redirectTarget]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resetSuccess =
    typeof location.state === "object" &&
    location.state &&
    "passwordResetSuccess" in location.state &&
    location.state.passwordResetSuccess === true;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const signedInUser = await login(email, password);
      if (signedInUser) {
        setPendingGuide(signedInUser.id);
      }
      navigate(redirectTarget, { replace: true });
    } catch (err) {
      setError(loginErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="relative mx-auto grid min-h-[calc(100vh-8rem)] w-full max-w-7xl items-center gap-6 overflow-hidden px-4 py-8 sm:px-6 lg:grid-cols-[1.02fr_0.98fr] lg:px-8">
      <div aria-hidden="true" className="pointer-events-none absolute -left-20 top-10 h-32 w-96 rotate-[-18deg] rounded-full bg-gradient-to-r from-cfb-pink/35 via-cfb-brand/30 to-transparent blur-2xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-24 top-24 h-32 w-[30rem] rotate-[-16deg] rounded-full bg-gradient-to-r from-transparent via-cfb-cyan/30 to-cfb-gold/24 blur-2xl" />
      <div aria-hidden="true" className="pointer-events-none absolute bottom-8 left-20 h-24 w-[26rem] rotate-[-10deg] rounded-full bg-gradient-to-r from-cfb-gold/24 via-cfb-brand/18 to-transparent blur-2xl" />

      <section className="relative hidden lg:block">
        <SurfaceCard variant="scoreboard" padding="spacious" className="cfb-playbook-pattern min-h-[560px]">
          <div className="relative flex h-full flex-col justify-between gap-10">
            <div className="space-y-7">
              <Link
                to="/"
                className="inline-flex items-center gap-2 rounded-full border border-cfb-brand/35 bg-cfb-brand/[0.12] px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-blue-100 transition hover:border-cfb-brand/55 hover:bg-cfb-brand/20"
              >
                <Trophy className="h-4 w-4 text-cfb-gold" aria-hidden="true" />
                CFB Fantasy
              </Link>

              <div className="max-w-2xl space-y-4">
                <p className="inline-flex items-center gap-2 rounded-full border border-cfb-gold/30 bg-cfb-gold/[0.10] px-4 py-2 text-[10px] font-black uppercase tracking-[0.2em] text-yellow-100">
                  <Zap className="h-3.5 w-3.5" aria-hidden="true" />
                  Game week starts here
                </p>
                <h1 className="cfb-display-title text-6xl leading-[0.92] xl:text-7xl">
                  Lock in your
                  <span className="block bg-gradient-to-r from-cfb-cyan via-cfb-brand to-cfb-gold bg-clip-text text-transparent">
                    title chase
                  </span>
                </h1>
                <p className="max-w-xl text-base font-semibold leading-7 text-cfb-text-secondary">
                  Sign in to manage your leagues, draft rooms, rosters, alerts, and matchup decisions
                  from one college football command center.
                </p>
              </div>
            </div>

            <div className="grid gap-3">
              {featureCards.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.title} className={`rounded-2xl border p-4 ${item.tone}`}>
                    <div className="flex items-start gap-3">
                      <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
                      <div>
                        <p className="text-sm font-black uppercase tracking-[0.12em] text-cfb-text-primary">
                          {item.title}
                        </p>
                        <p className="mt-1 text-sm font-medium leading-6 text-cfb-text-secondary">
                          {item.body}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </SurfaceCard>
      </section>

      <section className="relative mx-auto w-full max-w-[520px]">
        <SurfaceCard variant="raised" padding="none" className="relative overflow-hidden">
          <PlaybookDecor className="opacity-25" />
          <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-cfb-cyan via-cfb-gold to-cfb-pink" />

          <div className="relative space-y-8 p-6 sm:p-8">
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-cfb-gold via-cfb-cyan to-cfb-brand shadow-[0_0_38px_hsl(var(--brand-primary)/0.28)]">
                <Trophy className="h-7 w-7 text-slate-950" aria-hidden="true" />
              </div>
              <div>
                <p className="cfb-micro-label text-cfb-brand">Welcome back</p>
                <h2 className="mt-2 text-4xl font-black uppercase italic tracking-[-0.04em] text-cfb-text-primary">
                  Sign in
                </h2>
                <p className="mt-2 text-sm font-semibold text-cfb-text-secondary">
                  Continue to your leagues, draft rooms, and matchup dashboard.
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="login-email" className="ml-3 block text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">
                  Email address
                </label>
                <span className="group relative block">
                  <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted transition-colors group-focus-within:text-cfb-cyan" />
                  <Input
                    id="login-email"
                    type="email"
                    placeholder="coach@saturday.com"
                    className="h-14 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-12 text-sm font-bold text-cfb-text-primary placeholder:text-cfb-text-muted transition focus:border-cfb-brand/60 focus:ring-cfb-brand/25"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </span>
              </div>

              <div className="space-y-2">
                <span className="flex items-center justify-between px-3">
                  <label htmlFor="login-password" className="text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">
                    Password
                  </label>
                  <Link
                    to="/reset-password"
                    className="text-[9px] font-black uppercase tracking-widest text-cfb-gold transition hover:text-yellow-100 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    Reset Password
                  </Link>
                </span>
                <span className="group relative block">
                  <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted transition-colors group-focus-within:text-cfb-cyan" />
                  <Input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    className="h-14 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-12 pr-12 text-sm font-bold text-cfb-text-primary placeholder:text-cfb-text-muted transition focus:border-cfb-brand/60 focus:ring-cfb-brand/25"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((value) => !value)}
                    className="absolute right-4 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-cfb-text-muted transition hover:bg-white/10 hover:text-cfb-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-cyan/60"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </span>
              </div>

              {resetSuccess ? (
                <div className="rounded-2xl border border-cfb-gold/35 bg-cfb-gold/[0.12] px-4 py-3 text-xs font-bold text-yellow-100">
                  Password reset successfully. Sign in with your new password.
                </div>
              ) : null}

              {error ? (
                <div className="rounded-2xl border border-cfb-danger/35 bg-cfb-danger/[0.14] px-4 py-3 text-xs font-bold text-red-100">
                  {error}
                </div>
              ) : null}

              <Button
                type="submit"
                className="group h-14 w-full rounded-2xl bg-gradient-to-r from-cfb-cyan to-cfb-brand text-[11px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_18px_42px_hsl(var(--brand-primary)/0.26)] hover:brightness-110"
                disabled={isLoading}
              >
                {isLoading ? (
                  <span className="h-5 w-5 rounded-full border-2 border-slate-950/30 border-t-slate-950 animate-spin" />
                ) : (
                  <span className="flex items-center gap-2 transition-all group-hover:gap-4">
                    Sign in to dashboard <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </span>
                )}
              </Button>
            </form>

            <div className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/60 p-4">
              <div className="flex items-center gap-3">
                <CalendarClock className="h-5 w-5 text-cfb-gold" aria-hidden="true" />
                <p className="text-sm font-semibold text-cfb-text-secondary">
                  New commissioner? Create an account, then start a league.
                </p>
              </div>
            </div>
          </div>

          <div className="relative border-t border-cfb-border-subtle bg-cfb-surface/70 px-6 py-5 text-center">
            <p className="text-[10px] font-bold uppercase tracking-widest text-cfb-text-secondary">
              Don&apos;t have an account?
              <Link to="/signup" className="ml-1 font-black text-cfb-gold hover:text-yellow-100">
                Create one
              </Link>
            </p>
          </div>
        </SurfaceCard>
      </section>
    </main>
  );
}
