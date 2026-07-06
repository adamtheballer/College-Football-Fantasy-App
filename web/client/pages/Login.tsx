import React, { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { setPendingGuide } from "@/lib/onboarding";
import { ApiError } from "@/lib/api";
import {
  Trophy,
  Mail,
  Lock,
  ArrowRight,
  Github,
  Chrome,
  Apple,
  Zap,
  ShieldCheck,
  Sparkles,
  Users,
  Radio,
  Star,
  Eye,
  EyeOff,
} from "lucide-react";

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
  const initialNotice =
    typeof location.state === "object" &&
    location.state &&
    "notice" in location.state &&
    typeof location.state.notice === "string"
      ? location.state.notice
      : null;

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
  const [notice, setNotice] = useState<string | null>(initialNotice);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setNotice(null);
    try {
      const signedInUser = await login(email, password);
      if (signedInUser) {
        setPendingGuide(signedInUser.id);
      }
      navigate(redirectTarget, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (err instanceof ApiError && err.status === 0) {
        setError("Unable to reach the backend API. Start FastAPI on port 8000 and try again.");
      } else if (message.includes("invalid credentials")) {
        setError("Sign in failed. Check email/password and try again.");
      } else if (message.includes("Failed to fetch")) {
        setError("Cannot reach the server. Make sure backend is running on port 8000.");
      } else {
        setError("Sign in failed. Check email/password and try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative h-full max-h-full overflow-hidden rounded-[2rem] border border-white/10 bg-[#06111f] p-3 shadow-[0_0_80px_rgba(14,165,233,0.18)] sm:p-4 lg:p-5">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(34,211,238,0.34),transparent_34%),radial-gradient(circle_at_84%_18%,rgba(251,191,36,0.24),transparent_28%),radial-gradient(circle_at_70%_82%,rgba(244,63,94,0.22),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.15),rgba(2,6,23,0.88))]" />
      <div className="absolute inset-0 opacity-[0.16] [background-image:linear-gradient(rgba(255,255,255,0.16)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.16)_1px,transparent_1px)] [background-size:48px_48px]" />
      <div className="absolute left-8 right-8 top-1/2 h-px bg-gradient-to-r from-transparent via-white/35 to-transparent" />
      <div className="absolute bottom-8 left-1/2 h-28 w-28 -translate-x-1/2 rounded-full border-2 border-white/10" />

      <div className="relative grid h-full min-h-0 items-center gap-5 lg:grid-cols-[minmax(0,1fr)_440px]">
        <section className="hidden space-y-4 pl-2 lg:block xl:pl-6">
          <Link
            to="/"
            aria-label="Back to home"
            className="group inline-flex items-center gap-3 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100 shadow-[0_0_24px_rgba(34,211,238,0.18)] transition-all hover:border-cyan-200/50 hover:bg-cyan-300/15"
          >
            <Trophy className="h-4 w-4 text-amber-200 transition-transform group-hover:rotate-[-8deg] group-hover:scale-110" />
            CFB Fantasy
          </Link>

          <div className="max-w-3xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-200/25 bg-amber-300/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.24em] text-amber-100">
              <Sparkles className="h-3.5 w-3.5" />
              Saturday night is live
            </div>
            <h1 className="text-5xl font-black uppercase italic leading-[0.9] tracking-tight text-white xl:text-6xl">
              Build your
              <span className="block bg-gradient-to-r from-cyan-200 via-sky-300 to-amber-200 bg-clip-text text-transparent">
                title team
              </span>
            </h1>
            <p className="max-w-xl text-sm font-bold uppercase tracking-[0.16em] text-slate-200/70">
              Draft boards, live scoring, available-player tracking, and league bragging rights in one electric college football command center.
            </p>
          </div>

          <div className="grid max-w-2xl grid-cols-3 gap-3">
            {[
              { label: "Live Drafts", value: "90s", icon: Radio, tone: "from-cyan-400/25 to-blue-500/15 text-cyan-100" },
              { label: "Managers", value: "12", icon: Users, tone: "from-emerald-400/25 to-teal-500/15 text-emerald-100" },
              { label: "Power Plays", value: "24/7", icon: Star, tone: "from-amber-300/25 to-orange-500/15 text-amber-100" },
            ].map((item) => (
              <div key={item.label} className={`rounded-2xl border border-white/10 bg-gradient-to-br ${item.tone} p-3 shadow-[0_18px_40px_rgba(0,0,0,0.22)]`}>
                <item.icon className="mb-3 h-4 w-4" />
                <p className="text-xl font-black italic leading-none text-white">{item.value}</p>
                <p className="mt-2 text-[9px] font-black uppercase tracking-[0.18em] opacity-75">{item.label}</p>
              </div>
            ))}
          </div>

          <div className="flex max-w-xl flex-wrap gap-2">
            {["CFB rankings", "Rivalry week", "Available players", "Draft room"].map((label) => (
              <span key={label} className="rounded-full border border-white/10 bg-white/[0.08] px-3 py-1.5 text-[9px] font-black uppercase tracking-[0.18em] text-white/75">
                {label}
              </span>
            ))}
          </div>
        </section>

        <div className="mx-auto w-full max-w-[440px] animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="mb-3 flex flex-col items-center text-center lg:hidden">
            <Link
              to="/"
              aria-label="Back to home"
              className="mb-4 rounded-2xl bg-gradient-to-br from-cyan-300 to-blue-500 p-3 shadow-[0_0_30px_rgba(34,211,238,0.35)]"
            >
              <Trophy className="h-6 w-6 text-slate-950" />
            </Link>
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-100/80">College Football Fantasy</p>
          </div>

          <Card className="relative overflow-hidden rounded-[1.75rem] border border-white/15 bg-slate-950/72 shadow-[0_28px_80px_rgba(0,0,0,0.42)] backdrop-blur-2xl">
            <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-cyan-300 via-amber-200 to-rose-400" />
            <div className="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-cyan-400/18 blur-3xl" />
            <div className="absolute -bottom-20 left-8 h-44 w-44 rounded-full bg-rose-400/14 blur-3xl" />

            <CardContent className="relative space-y-5 p-5 sm:p-6">
              <div className="space-y-2 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-200 via-cyan-300 to-blue-500 shadow-[0_0_38px_rgba(34,211,238,0.34)]">
                  <Trophy className="h-5 w-5 text-slate-950" />
                </div>
                <div>
                  <h2 className="text-3xl font-black uppercase italic tracking-tight text-white">
                    Welcome Back
                  </h2>
                  <p className="mt-1 text-[9px] font-black uppercase tracking-[0.24em] text-cyan-100/60">
                    Lock in and run your league
                  </p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-3">
                  <div className="space-y-2">
                    <label className="ml-3 text-[10px] font-black uppercase tracking-widest text-cyan-100/70">Email Address</label>
                    <div className="group relative">
                      <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                      <Input
                        type="email"
                        placeholder="coach@saturday.com"
                        className="h-12 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-sm font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between px-3">
                      <label className="text-[10px] font-black uppercase tracking-widest text-cyan-100/70">Password</label>
                      <Link
                        to="/password-reset"
                        className="text-[9px] font-black uppercase tracking-widest text-amber-200/80 transition-colors hover:text-amber-100"
                      >
                        Forgot Password?
                      </Link>
                    </div>
                    <div className="group relative">
                      <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                      <Input
                        type={showPassword ? "text" : "password"}
                        placeholder="••••••••"
                        className="h-12 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 pr-12 text-sm font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
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
                </div>

                {error && (
                  <div className="rounded-2xl border border-red-300/35 bg-red-500/15 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-red-100">
                    {error}
                  </div>
                )}

                {notice && (
                  <div className="rounded-2xl border border-emerald-200/35 bg-emerald-300/12 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-100">
                    {notice}
                  </div>
                )}

                <Button
                  type="submit"
                  className="group h-12 w-full overflow-hidden rounded-2xl bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-[10px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_18px_42px_rgba(14,165,233,0.32)] transition-all hover:brightness-110"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <div className="h-5 w-5 rounded-full border-2 border-slate-950/30 border-t-slate-950 animate-spin" />
                  ) : (
                    <span className="flex items-center gap-2 transition-all group-hover:gap-4">
                      Sign In to Dashboard <ArrowRight className="h-4 w-4" />
                    </span>
                  )}
                </Button>
              </form>

              <div className="relative flex items-center justify-center">
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-white/20 to-white/10" />
                <span className="px-4 text-[9px] font-black uppercase tracking-widest text-slate-300/50">Or continue with</span>
                <div className="h-px flex-1 bg-gradient-to-l from-transparent via-white/20 to-white/10" />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <Button variant="outline" className="h-11 rounded-2xl border-white/10 bg-white/10 text-white hover:border-cyan-200/35 hover:bg-cyan-300/15">
                  <Chrome className="h-5 w-5" />
                </Button>
                <Button variant="outline" className="h-11 rounded-2xl border-white/10 bg-white/10 text-white hover:border-amber-200/35 hover:bg-amber-300/15">
                  <Apple className="h-5 w-5" />
                </Button>
                <Button variant="outline" className="h-11 rounded-2xl border-white/10 bg-white/10 text-white hover:border-rose-200/35 hover:bg-rose-300/15">
                  <Github className="h-5 w-5" />
                </Button>
              </div>
            </CardContent>

            <div className="relative border-t border-white/10 bg-white/[0.06] px-6 py-3 text-center">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-300/70">
                Don't have an account? <Link to="/signup" className="ml-1 font-black text-amber-200 hover:text-amber-100">Create One</Link>
              </p>
            </div>
          </Card>

          <div className="mt-3 flex items-center justify-center gap-5 text-slate-200/55">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-200" />
              <span className="text-[8px] font-black uppercase tracking-widest">Secure SSL</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-3.5 w-3.5 text-amber-200" />
              <span className="text-[8px] font-black uppercase tracking-widest">Live Scoring</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
