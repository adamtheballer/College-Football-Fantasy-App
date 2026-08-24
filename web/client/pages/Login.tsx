import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Eye,
  EyeOff,
  Lock,
  Mail,
  ShieldCheck,
  Trophy,
  User,
  Users,
  Zap,
} from "lucide-react";

import { PlaybookDecor, SurfaceCard } from "@/components/fantasy";
import { PublicLegalLinks } from "@/components/legal/PublicLegalLinks";
import { useRuntimeCapabilities } from "@/components/RuntimeCompatibilityGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { ApiError, apiUnavailableMessage } from "@/lib/api";
import { setPendingGuide } from "@/lib/onboarding";
import { PASSWORD_POLICY_MESSAGE, passwordMeetsPolicy } from "@/lib/password-policy";

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

export type LoginMode = "signin" | "signup";

export const initialLoginMode = (flow: string | null, _earlyAccessProEnabled: boolean): LoginMode => {
  if (flow === "signup") return "signup";
  // Retire old Pro-code links without letting them surface an obsolete claim
  // workflow in the alpha release.
  return "signin";
};

export const loginPathForMode = (mode: LoginMode) =>
  mode === "signin" ? "/login" : "/login?flow=signup";

/**
 * Protected routes place a same-app pathname in history state before sending a
 * visitor to sign in. Treat that state as untrusted on the way back so a
 * modified browser history entry can never become an external redirect.
 */
export const safeAuthRedirectTarget = (value: unknown): string => {
  if (typeof value !== "string") return "/";

  const candidate = value.trim();
  if (!candidate.startsWith("/") || candidate.startsWith("//") || candidate.includes("\\")) {
    return "/";
  }

  try {
    const parsed = new URL(candidate, "https://cfbfantasy.local");
    return parsed.origin === "https://cfbfantasy.local"
      ? `${parsed.pathname}${parsed.search}${parsed.hash}`
      : "/";
  } catch {
    return "/";
  }
};

export const shouldHoldAuthEntry = (
  isBootstrapping: boolean,
  isLoggedIn: boolean,
  holdPostSignupRedirect: boolean,
) => isBootstrapping || (isLoggedIn && !holdPostSignupRedirect);

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, signup, isBootstrapping, isLoggedIn } = useAuth();
  const {
    email_enabled: emailEnabled,
    password_reset_enabled: passwordResetEnabled,
  } = useRuntimeCapabilities();
  const redirectTarget = safeAuthRedirectTarget(
    typeof location.state === "object" && location.state && "from" in location.state
      ? location.state.from
      : undefined,
  );

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [mode, setMode] = useState<LoginMode>(
    () => initialLoginMode(new URLSearchParams(location.search).get("flow"), false),
  );
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resetSuccess =
    typeof location.state === "object" &&
    location.state &&
    "passwordResetSuccess" in location.state &&
    location.state.passwordResetSuccess === true;
  useEffect(() => {
    if (isLoggedIn) {
      navigate(redirectTarget, { replace: true });
    }
  }, [isLoggedIn, navigate, redirectTarget]);

  const selectMode = (nextMode: LoginMode, clearError = true) => {
    if (clearError) setError(null);
    setMode(nextMode);
    navigate(loginPathForMode(nextMode), { replace: true });
  };

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

  const handleSignupSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!passwordMeetsPolicy(password)) {
      setError(PASSWORD_POLICY_MESSAGE);
      return;
    }
    setIsLoading(true);
    try {
      const nextUser = await signup(firstName, email, password);
      setPendingGuide(nextUser.id);
      setPassword("");
      navigate(redirectTarget, { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 0) {
        setError(apiUnavailableMessage());
      } else if (caught instanceof Error && caught.message.includes("409")) {
        setError("That email is already registered. Try signing in instead.");
      } else if (caught instanceof Error && caught.message) {
        setError(caught.message);
      } else {
        setError("Create account failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // A remembered user is validated by AuthProvider before this route becomes
  // interactive. That keeps returning users out of sign-in and signup forms
  // unless they deliberately sign out first.
  if (shouldHoldAuthEntry(isBootstrapping, isLoggedIn, false)) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-8rem)] w-full max-w-xl items-center justify-center px-4 py-8">
        <p className="cfb-micro-label text-center text-cfb-text-secondary" role="status">
          Restoring your signed-in session…
        </p>
      </main>
    );
  }

  return (
    <main className="relative mx-auto grid min-h-[calc(100vh-8rem)] w-full max-w-7xl items-center gap-6 overflow-hidden px-4 py-8 sm:px-6 lg:grid-cols-[1.02fr_0.98fr] lg:px-8">
      <div aria-hidden="true" className="pointer-events-none absolute -left-20 top-10 h-32 w-96 rotate-[-18deg] rounded-full bg-gradient-to-r from-cfb-crimson/35 via-cfb-brand/30 to-transparent blur-2xl" />
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
                College Fantasy Football
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
          <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-cfb-cyan via-cfb-gold to-cfb-crimson" />

          <div className="relative space-y-8 p-6 sm:p-8">
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-cfb-gold via-cfb-cyan to-cfb-brand shadow-[0_0_38px_hsl(var(--brand-primary)/0.28)]">
                <Trophy className="h-7 w-7 text-slate-950" aria-hidden="true" />
              </div>
              <div>
                <p className="cfb-micro-label text-cfb-brand">
                  {mode === "signin" ? "Welcome back" : "Create your account"}
                </p>
                <h2 className="cfb-display-title mt-2 text-4xl italic text-cfb-text-primary">
                  {mode === "signin" ? "Sign in" : "Create account"}
                </h2>
                <p className="mt-2 text-sm font-semibold text-cfb-text-secondary">
                  {mode === "signin"
                    ? "Continue to your leagues, draft rooms, and matchup dashboard."
                    : "No invitation code is needed to create your account."}
                </p>
              </div>
            </div>

            {mode === "signin" ? (
              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <label htmlFor="login-email" className="ml-3 block text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">Email address</label>
                  <span className="group relative block">
                    <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted transition-colors group-focus-within:text-cfb-cyan" />
                    <Input id="login-email" type="email" placeholder="coach@saturday.com" className="h-14 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-12 text-base font-bold text-cfb-text-primary placeholder:text-cfb-text-muted transition focus:border-cfb-brand/60 focus:ring-cfb-brand/25 md:text-sm" value={email} onChange={(e) => setEmail(e.target.value)} required />
                  </span>
                </div>
                <div className="space-y-2">
                  <span className="flex items-center justify-between px-3">
                    <label htmlFor="login-password" className="text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">Password</label>
                    {emailEnabled && passwordResetEnabled ? (
                      <Link to="/forgot-password" className="text-[9px] font-black uppercase tracking-widest text-cfb-gold transition hover:text-yellow-100">Forgot password?</Link>
                    ) : null}
                  </span>
                  <span className="group relative block">
                    <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted transition-colors group-focus-within:text-cfb-cyan" />
                    <Input id="login-password" type={showPassword ? "text" : "password"} placeholder="••••••••" className="h-14 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-12 pr-12 text-base font-bold text-cfb-text-primary placeholder:text-cfb-text-muted transition focus:border-cfb-brand/60 focus:ring-cfb-brand/25 md:text-sm" value={password} onChange={(e) => setPassword(e.target.value)} required />
                    <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword((value) => !value)} className="absolute right-4 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-cfb-text-muted transition hover:bg-white/10 hover:text-cfb-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-cyan/60">
                      {showPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                    </button>
                  </span>
                </div>
                {resetSuccess ? <div className="rounded-2xl border border-cfb-gold/35 bg-cfb-gold/[0.12] px-4 py-3 text-xs font-bold text-yellow-100">Password reset successfully. Sign in with your new password.</div> : null}
                {error ? <div role="alert" className="rounded-2xl border border-cfb-danger/35 bg-cfb-danger/[0.14] px-4 py-3 text-xs font-bold text-red-100">{error}</div> : null}
                <Button type="submit" className="group h-14 w-full rounded-2xl bg-gradient-to-r from-cfb-cyan to-cfb-brand text-[11px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_18px_42px_hsl(var(--brand-primary)/0.26)] hover:brightness-110" disabled={isLoading}>
                  {isLoading ? <span className="h-5 w-5 rounded-full border-2 border-slate-950/30 border-t-slate-950 animate-spin" /> : <span className="flex items-center gap-2 transition-all group-hover:gap-4">Sign in to dashboard <ArrowRight className="h-4 w-4" aria-hidden="true" /></span>}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleSignupSubmit} className="space-y-5">
                <div className="space-y-2"><label htmlFor="signup-name" className="ml-3 block text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">First name</label><span className="group relative block"><User className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted" /><Input id="signup-name" type="text" placeholder="Your first name" maxLength={50} className="h-14 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-12 text-base font-bold text-cfb-text-primary md:text-sm" value={firstName} onChange={(event) => setFirstName(event.target.value)} required /></span></div>
                <div className="space-y-2"><label htmlFor="signup-email" className="ml-3 block text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">Email address</label><span className="group relative block"><Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted" /><Input id="signup-email" type="email" placeholder="coach@saturday.com" className="h-14 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-12 text-base font-bold text-cfb-text-primary md:text-sm" value={email} onChange={(event) => setEmail(event.target.value)} required /></span></div>
                <div className="space-y-2"><label htmlFor="signup-password" className="ml-3 block text-[10px] font-black uppercase tracking-widest text-cfb-text-muted">Password</label><span className="group relative block"><Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted" /><Input id="signup-password" type={showPassword ? "text" : "password"} placeholder="••••••••" className="h-14 rounded-2xl border-cfb-border-subtle bg-cfb-surface/80 pl-12 pr-12 text-base font-bold text-cfb-text-primary md:text-sm" value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((value) => !value)} className="absolute right-4 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-cfb-text-muted">{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></span></div>
                <p className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/60 px-4 py-3 text-xs font-semibold text-cfb-text-secondary">{PASSWORD_POLICY_MESSAGE}</p>
                {error ? <div role="alert" className="rounded-2xl border border-cfb-danger/35 bg-cfb-danger/[0.14] px-4 py-3 text-xs font-bold text-red-100">{error}</div> : null}
                <Button type="submit" className="group h-14 w-full rounded-2xl bg-gradient-to-r from-cfb-cyan to-cfb-brand text-[11px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_18px_42px_hsl(var(--brand-primary)/0.26)] hover:brightness-110" disabled={isLoading}>{isLoading ? <span className="h-5 w-5 rounded-full border-2 border-slate-950/30 border-t-slate-950 animate-spin" /> : <span className="flex items-center gap-2 transition-all group-hover:gap-4">Create account <ArrowRight className="h-4 w-4" aria-hidden="true" /></span>}</Button>
              </form>
            )}

            <div className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/60 p-4">
              <p className="text-sm font-semibold text-cfb-text-secondary">{mode === "signin" ? "New here? Create your account to get started." : "Already have an account? Sign in to continue."}</p>
            </div>
          </div>

          <div className="relative border-t border-cfb-border-subtle bg-cfb-surface/70 px-6 py-5 text-center">
            {mode === "signin" ? <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-[10px] font-bold uppercase tracking-widest text-cfb-text-secondary"><button type="button" onClick={() => selectMode("signup")}>Don&apos;t have an account?<span className="ml-1 font-black text-cfb-gold hover:text-yellow-100">Create one</span></button></div> : <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-[10px] font-bold uppercase tracking-widest text-cfb-text-secondary"><button type="button" onClick={() => selectMode("signin")}>Already have an account?<span className="ml-1 font-black text-cfb-gold hover:text-yellow-100">Sign in</span></button></div>}
          </div>
        </SurfaceCard>
        <div className="mt-5 text-center text-[11px] font-semibold text-cfb-text-muted">
          <PublicLegalLinks />
        </div>
      </section>

    </main>
  );
}
