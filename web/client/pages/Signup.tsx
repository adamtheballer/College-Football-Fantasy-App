import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { setPendingGuide } from "@/lib/onboarding";
import { ApiError, apiUnavailableMessage } from "@/lib/api";
import { PASSWORD_POLICY_MESSAGE, passwordMeetsPolicy, passwordPolicyChecks } from "@/lib/password-policy";
import { PublicLegalLinks } from "@/components/legal/PublicLegalLinks";
import { clearBetaAccessReservation, getBetaAccessReservation } from "@/lib/beta-access";
import {
  Trophy,
  Mail,
  Lock,
  User,
  ArrowRight,
  Github,
  Chrome,
  Apple,
  Eye,
  EyeOff,
  Zap,
  ShieldCheck,
  Sparkles,
  Users,
  Radio,
  Star,
} from "lucide-react";

export default function Signup() {
  const navigate = useNavigate();
  const { signup, isBootstrapping, isLoggedIn } = useAuth();
  const reservation = getBetaAccessReservation();
  const [firstName, setFirstName] = useState("");
  const [email, setEmail] = useState(reservation?.email ?? "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const passwordChecks = passwordPolicyChecks(password);
  const isPasswordStrong = passwordMeetsPolicy(password);

  useEffect(() => {
    if (!isBootstrapping && isLoggedIn) {
      navigate("/", { replace: true });
    }
  }, [isBootstrapping, isLoggedIn, navigate]);

  if (isBootstrapping || isLoggedIn) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-8rem)] w-full max-w-xl items-center justify-center px-4 py-8">
        <p className="cfb-micro-label text-center text-cfb-text-secondary" role="status">
          Restoring your signed-in session…
        </p>
      </main>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!isPasswordStrong) {
      setError(PASSWORD_POLICY_MESSAGE);
      return;
    }
    setIsLoading(true);
    try {
      const nextUser = await signup(firstName, email, password, reservation?.token);
      clearBetaAccessReservation();
      setPendingGuide(nextUser.id);
      navigate("/", { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (err instanceof ApiError && err.status === 0) {
        setError(apiUnavailableMessage());
      } else if (message.includes("409")) {
        setError("That email is already registered. Try signing in instead.");
      } else if (message) {
        setError(message);
      } else {
        setError("Create account failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative h-[calc(100vh-4rem)] min-h-[620px] overflow-hidden rounded-md border border-white/10 bg-cfb-canvas p-4 shadow-none sm:p-5 lg:min-h-0 lg:p-6">
      <div className="relative grid h-full min-h-0 items-center gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(380px,460px)]">
        <section className="hidden max-h-full space-y-5 overflow-hidden pl-2 xl:block xl:pl-6">
          <Link
            to="/"
            aria-label="Back to home"
            className="group inline-flex items-center gap-3 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.06em] text-cyan-100 shadow-none transition-all hover:border-cyan-200/50 hover:bg-cyan-300/15"
          >
            <Trophy className="h-4 w-4 text-amber-200 transition-transform group-hover:rotate-[-8deg] group-hover:scale-110" />
            College Fantasy Football
          </Link>

          <div className="max-w-3xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-200/25 bg-amber-300/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.06em] text-amber-100">
              <Sparkles className="h-3.5 w-3.5" />
              Saturday night is live
            </div>
            <h1 className="cfb-display-title text-4xl xl:text-5xl">
              Build your
              <span className="block text-cfb-brand">
                title team
              </span>
            </h1>
            <p className="max-w-xl text-xs font-bold uppercase tracking-[0.06em] text-slate-200/70 xl:text-sm">
              Draft boards, live scoring, available-player tracking, and league bragging rights in one electric college football command center.
            </p>
          </div>

          <div className="grid max-w-2xl grid-cols-3 gap-3 [@media(max-height:760px)]:hidden">
            {[
              { label: "Live Drafts", value: "90s", icon: Radio, tone: "from-cyan-400/25 to-blue-500/15 text-cyan-100" },
              { label: "Managers", value: "12", icon: Users, tone: "from-emerald-400/25 to-teal-500/15 text-emerald-100" },
              { label: "Power Plays", value: "24/7", icon: Star, tone: "from-amber-300/25 to-orange-500/15 text-amber-100" },
            ].map((item) => (
              <div key={item.label} className="rounded-md border border-cfb-border-subtle bg-cfb-surface p-4 text-cfb-text-secondary">
                <item.icon className="mb-4 h-5 w-5" />
                <p className="text-2xl font-black italic leading-none text-white">{item.value}</p>
                <p className="mt-2 text-[9px] font-black uppercase tracking-[0.06em] opacity-75">{item.label}</p>
              </div>
            ))}
          </div>

          <div className="flex max-w-xl flex-wrap gap-3 [@media(max-height:760px)]:hidden">
            {["CFB rankings", "League matchups", "Available players", "Draft room"].map((label) => (
              <span key={label} className="rounded-full border border-white/10 bg-white/[0.08] px-4 py-2 text-[10px] font-black uppercase tracking-[0.06em] text-white/75">
                {label}
              </span>
            ))}
          </div>
        </section>

        <div className="mx-auto flex max-h-full w-full max-w-[460px] flex-col justify-center animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="mb-5 flex flex-col items-center text-center lg:hidden">
            <Link
              to="/"
              aria-label="Back to home"
              className="mb-4 rounded-md bg-cfb-brand p-3"
            >
              <Trophy className="h-6 w-6 text-slate-950" />
            </Link>
            <p className="text-[10px] font-black uppercase tracking-[0.06em] text-cyan-100/80">College Football Fantasy</p>
          </div>

          <Card className="relative max-h-full overflow-hidden rounded-md border border-cfb-border-subtle bg-cfb-surface shadow-none">
            <div className="absolute inset-x-0 top-0 h-0.5 bg-cfb-brand" />

            <CardContent className="relative space-y-4 p-5 sm:p-6 xl:p-7 [@media(max-height:760px)]:space-y-3 [@media(max-height:760px)]:p-4">
              <div className="space-y-2 text-center [@media(max-height:760px)]:space-y-1">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-md bg-cfb-brand [@media(max-height:760px)]:hidden">
                  <Trophy className="h-6 w-6 text-slate-950" />
                </div>
                <div>
                  <h2 className="text-3xl font-black uppercase italic tracking-tight text-white sm:text-4xl [@media(max-height:760px)]:text-2xl">
                    Create Account
                  </h2>
                  <p className="mt-2 text-[10px] font-black uppercase tracking-[0.06em] text-cyan-100/60 [@media(max-height:760px)]:hidden">
                    Start building your league
                  </p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-3 [@media(max-height:760px)]:space-y-2.5">
                <div className="space-y-3 [@media(max-height:760px)]:space-y-2">
                  <div className="space-y-1.5">
                    <label className="ml-3 text-[10px] font-black uppercase tracking-widest text-cyan-100/70">First Name</label>
                    <div className="group relative">
                      <User className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                      <Input
                        type="text"
                        placeholder="Enter your first name"
                        className="h-11 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-base font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25 sm:h-12 sm:text-sm [@media(max-height:760px)]:h-10"
                        value={firstName}
                        maxLength={50}
                        onChange={(e) => setFirstName(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="ml-3 text-[10px] font-black uppercase tracking-widest text-cyan-100/70">Email Address</label>
                    <div className="group relative">
                      <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                      <Input
                        type="email"
                        placeholder="coach@saturday.com"
                        className="h-11 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-base font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25 sm:h-12 sm:text-sm [@media(max-height:760px)]:h-10"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        readOnly={Boolean(reservation)}
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between px-3">
                      <label className="text-[10px] font-black uppercase tracking-widest text-cyan-100/70">Password</label>
                      <Link
                        to="/login"
                        className="text-[9px] font-black uppercase tracking-widest text-amber-200/80 transition-colors hover:text-amber-100"
                      >
                        Already Registered?
                      </Link>
                    </div>
                    <div className="group relative">
                      <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                      <Input
                        id="signup-password"
                        type={showPassword ? "text" : "password"}
                        placeholder="••••••••"
                        className="h-11 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 pr-12 text-base font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25 sm:h-12 sm:text-sm [@media(max-height:760px)]:h-10"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                      />
                      <button
                        type="button"
                        aria-label={showPassword ? "Hide password" : "Show password"}
                        aria-pressed={showPassword}
                        onClick={() => setShowPassword((value) => !value)}
                        className="absolute right-4 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-cyan-100/60 transition hover:bg-white/10 hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200/70"
                      >
                        {showPassword ? (
                          <EyeOff className="h-4 w-4" aria-hidden="true" />
                        ) : (
                          <Eye className="h-4 w-4" aria-hidden="true" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 rounded-2xl border border-cyan-200/10 bg-white/[0.06] p-3 [@media(max-height:760px)]:hidden" aria-live="polite">
                  {passwordChecks.map((check) => (
                    <div
                      key={check.label}
                      className={`flex items-center gap-2 text-[9px] font-black uppercase tracking-[0.06em] ${
                        check.isValid ? "text-emerald-100" : "text-slate-300/50"
                      }`}
                    >
                      <span
                        className={`h-2 w-2 rounded-full ${
                          check.isValid
                            ? "bg-emerald-300 shadow-none"
                            : "bg-slate-500/60"
                        }`}
                      />
                      {check.label}
                    </div>
                  ))}
                </div>

                {error && (
                  <div className="rounded-2xl border border-red-300/35 bg-red-500/15 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-red-100">
                    {error}
                  </div>
                )}

                <Button
                  type="submit"
                  className="group h-12 w-full overflow-hidden rounded-md bg-cfb-brand text-sm font-semibold text-primary-foreground transition-colors hover:bg-cfb-brand-hover [@media(max-height:760px)]:h-11"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <div className="h-5 w-5 rounded-full border-2 border-slate-950/30 border-t-slate-950 animate-spin" />
                  ) : (
                    <span className="flex items-center gap-2 transition-all group-hover:gap-4">
                      Create Account <ArrowRight className="h-4 w-4" />
                    </span>
                  )}
                </Button>
              </form>

              <div className="space-y-4 [@media(max-height:760px)]:hidden">
                <div className="relative flex items-center justify-center">
                  <div className="h-px flex-1 bg-gradient-to-r from-transparent via-white/20 to-white/10" />
                  <span className="px-4 text-[9px] font-black uppercase tracking-widest text-slate-300/50">Or continue with</span>
                  <div className="h-px flex-1 bg-gradient-to-l from-transparent via-white/20 to-white/10" />
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <Button variant="outline" className="h-12 rounded-2xl border-white/10 bg-white/10 text-white hover:border-cyan-200/35 hover:bg-cyan-300/15">
                    <Chrome className="h-5 w-5" />
                  </Button>
                  <Button variant="outline" className="h-12 rounded-2xl border-white/10 bg-white/10 text-white hover:border-amber-200/35 hover:bg-amber-300/15">
                    <Apple className="h-5 w-5" />
                  </Button>
                  <Button variant="outline" className="h-12 rounded-2xl border-white/10 bg-white/10 text-white hover:border-rose-200/35 hover:bg-rose-300/15">
                    <Github className="h-5 w-5" />
                  </Button>
                </div>
              </div>
            </CardContent>

            <div className="relative border-t border-white/10 bg-white/[0.06] px-7 py-4 text-center [@media(max-height:760px)]:hidden">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-300/70">
                Already have an account? <Link to="/login" className="ml-1 font-black text-amber-200 hover:text-amber-100">Sign In</Link>
              </p>
            </div>
          </Card>

          <div className="mt-4 flex items-center justify-center gap-5 text-slate-200/55 [@media(max-height:760px)]:hidden">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-200" />
              <span className="text-[8px] font-black uppercase tracking-widest">Secure SSL</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-3.5 w-3.5 text-amber-200" />
              <span className="text-[8px] font-black uppercase tracking-widest">Live Scoring</span>
            </div>
          </div>
          <div className="mt-4 text-center text-[10px] font-bold uppercase tracking-widest text-slate-200/55 [@media(max-height:760px)]:hidden">
            <PublicLegalLinks />
          </div>
        </div>
      </div>
    </div>
  );
}
