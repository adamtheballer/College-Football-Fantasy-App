import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
  User,
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
} from "lucide-react";

export default function Signup() {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const passwordPolicyMessage =
    "Password must be at least 12 characters and include one uppercase letter, one number, and one special character.";
  const passwordChecks = [
    { label: "12+ characters", isValid: password.length >= 12 },
    { label: "One uppercase letter", isValid: /[A-Z]/.test(password) },
    { label: "One number", isValid: /\d/.test(password) },
    { label: "One special character", isValid: /[^A-Za-z0-9]/.test(password) },
  ];
  const isPasswordStrong = passwordChecks.every((check) => check.isValid);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!isPasswordStrong) {
      setError(passwordPolicyMessage);
      return;
    }
    setIsLoading(true);
    try {
      const nextUser = await signup(firstName, email, password);
      if (nextUser) {
        setPendingGuide(nextUser.id);
      }
      navigate("/", { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (err instanceof ApiError && err.status === 0) {
        setError("Unable to reach the backend API. Start FastAPI on port 8000 and try again.");
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
    <div className="relative min-h-[calc(100vh-8rem)] overflow-hidden rounded-[2.25rem] border border-white/10 bg-[#06111f] p-4 shadow-[0_0_80px_rgba(14,165,233,0.18)] sm:p-6 lg:p-8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(34,211,238,0.34),transparent_34%),radial-gradient(circle_at_84%_18%,rgba(251,191,36,0.24),transparent_28%),radial-gradient(circle_at_70%_82%,rgba(244,63,94,0.22),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.15),rgba(2,6,23,0.88))]" />
      <div className="absolute inset-0 opacity-[0.16] [background-image:linear-gradient(rgba(255,255,255,0.16)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.16)_1px,transparent_1px)] [background-size:48px_48px]" />
      <div className="absolute left-8 right-8 top-1/2 h-px bg-gradient-to-r from-transparent via-white/35 to-transparent" />
      <div className="absolute bottom-8 left-1/2 h-40 w-40 -translate-x-1/2 rounded-full border-2 border-white/10" />

      <div className="relative grid min-h-[calc(100vh-12rem)] items-center gap-8 lg:grid-cols-[minmax(0,1fr)_480px]">
        <section className="hidden space-y-7 pl-2 lg:block xl:pl-8">
          <Link
            to="/"
            aria-label="Back to home"
            className="group inline-flex items-center gap-3 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100 shadow-[0_0_24px_rgba(34,211,238,0.18)] transition-all hover:border-cyan-200/50 hover:bg-cyan-300/15"
          >
            <Trophy className="h-4 w-4 text-amber-200 transition-transform group-hover:rotate-[-8deg] group-hover:scale-110" />
            CFB Fantasy
          </Link>

          <div className="max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-200/25 bg-amber-300/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.24em] text-amber-100">
              <Sparkles className="h-3.5 w-3.5" />
              Saturday night is live
            </div>
            <h1 className="text-6xl font-black uppercase italic leading-[0.9] tracking-tight text-white xl:text-7xl">
              Build your
              <span className="block bg-gradient-to-r from-cyan-200 via-sky-300 to-amber-200 bg-clip-text text-transparent">
                title team
              </span>
            </h1>
            <p className="max-w-xl text-sm font-bold uppercase tracking-[0.16em] text-slate-200/70">
              Draft boards, live scoring, waiver runs, and league bragging rights in one electric college football command center.
            </p>
          </div>

          <div className="grid max-w-2xl grid-cols-3 gap-3">
            {[
              { label: "Live Drafts", value: "90s", icon: Radio, tone: "from-cyan-400/25 to-blue-500/15 text-cyan-100" },
              { label: "Managers", value: "12", icon: Users, tone: "from-emerald-400/25 to-teal-500/15 text-emerald-100" },
              { label: "Power Plays", value: "24/7", icon: Star, tone: "from-amber-300/25 to-orange-500/15 text-amber-100" },
            ].map((item) => (
              <div key={item.label} className={`rounded-2xl border border-white/10 bg-gradient-to-br ${item.tone} p-4 shadow-[0_18px_40px_rgba(0,0,0,0.22)]`}>
                <item.icon className="mb-4 h-5 w-5" />
                <p className="text-2xl font-black italic leading-none text-white">{item.value}</p>
                <p className="mt-2 text-[9px] font-black uppercase tracking-[0.18em] opacity-75">{item.label}</p>
              </div>
            ))}
          </div>

          <div className="flex max-w-xl flex-wrap gap-3">
            {["CFB rankings", "Rivalry week", "Waiver wire", "Draft room"].map((label) => (
              <span key={label} className="rounded-full border border-white/10 bg-white/[0.08] px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-white/75">
                {label}
              </span>
            ))}
          </div>
        </section>

        <div className="mx-auto w-full max-w-[480px] animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="mb-5 flex flex-col items-center text-center lg:hidden">
            <Link
              to="/"
              aria-label="Back to home"
              className="mb-4 rounded-2xl bg-gradient-to-br from-cyan-300 to-blue-500 p-3 shadow-[0_0_30px_rgba(34,211,238,0.35)]"
            >
              <Trophy className="h-6 w-6 text-slate-950" />
            </Link>
            <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-100/80">College Football Fantasy</p>
          </div>

          <Card className="relative overflow-hidden rounded-[2rem] border border-white/15 bg-slate-950/72 shadow-[0_28px_80px_rgba(0,0,0,0.42)] backdrop-blur-2xl">
            <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-cyan-300 via-amber-200 to-rose-400" />
            <div className="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-cyan-400/18 blur-3xl" />
            <div className="absolute -bottom-20 left-8 h-44 w-44 rounded-full bg-rose-400/14 blur-3xl" />

            <CardContent className="relative space-y-8 p-7 sm:p-9">
              <div className="space-y-3 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-200 via-cyan-300 to-blue-500 shadow-[0_0_38px_rgba(34,211,238,0.34)]">
                  <Trophy className="h-7 w-7 text-slate-950" />
                </div>
                <div>
                  <h2 className="text-4xl font-black uppercase italic tracking-tight text-white">
                    Create Account
                  </h2>
                  <p className="mt-2 text-[10px] font-black uppercase tracking-[0.28em] text-cyan-100/60">
                    Start building your league
                  </p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="ml-3 text-[10px] font-black uppercase tracking-widest text-cyan-100/70">First Name</label>
                    <div className="group relative">
                      <User className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                      <Input
                        type="text"
                        placeholder="Enter your first name"
                        className="h-14 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-sm font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="ml-3 text-[10px] font-black uppercase tracking-widest text-cyan-100/70">Email Address</label>
                    <div className="group relative">
                      <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                      <Input
                        type="email"
                        placeholder="coach@saturday.com"
                        className="h-14 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-sm font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25"
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
                        to="/login"
                        className="text-[9px] font-black uppercase tracking-widest text-amber-200/80 transition-colors hover:text-amber-100"
                      >
                        Already Registered?
                      </Link>
                    </div>
                    <div className="group relative">
                      <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                      <Input
                        type="password"
                        placeholder="••••••••"
                        className="h-14 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-sm font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                </div>

                <div className="grid gap-2 rounded-2xl border border-cyan-200/10 bg-white/[0.06] p-3" aria-live="polite">
                  {passwordChecks.map((check) => (
                    <div
                      key={check.label}
                      className={`flex items-center gap-2 text-[9px] font-black uppercase tracking-[0.14em] ${
                        check.isValid ? "text-emerald-100" : "text-slate-300/50"
                      }`}
                    >
                      <span
                        className={`h-2 w-2 rounded-full ${
                          check.isValid
                            ? "bg-emerald-300 shadow-[0_0_12px_rgba(110,231,183,0.7)]"
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
                  className="group h-14 w-full overflow-hidden rounded-2xl bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-[11px] font-black uppercase tracking-[0.22em] text-slate-950 shadow-[0_18px_42px_rgba(14,165,233,0.32)] transition-all hover:brightness-110"
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

              <div className="relative flex items-center justify-center">
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-white/20 to-white/10" />
                <span className="px-4 text-[9px] font-black uppercase tracking-widest text-slate-300/50">Or continue with</span>
                <div className="h-px flex-1 bg-gradient-to-l from-transparent via-white/20 to-white/10" />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <Button variant="outline" className="h-14 rounded-2xl border-white/10 bg-white/10 text-white hover:border-cyan-200/35 hover:bg-cyan-300/15">
                  <Chrome className="h-5 w-5" />
                </Button>
                <Button variant="outline" className="h-14 rounded-2xl border-white/10 bg-white/10 text-white hover:border-amber-200/35 hover:bg-amber-300/15">
                  <Apple className="h-5 w-5" />
                </Button>
                <Button variant="outline" className="h-14 rounded-2xl border-white/10 bg-white/10 text-white hover:border-rose-200/35 hover:bg-rose-300/15">
                  <Github className="h-5 w-5" />
                </Button>
              </div>
            </CardContent>

            <div className="relative border-t border-white/10 bg-white/[0.06] px-7 py-5 text-center">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-300/70">
                Already have an account? <Link to="/login" className="ml-1 font-black text-amber-200 hover:text-amber-100">Sign In</Link>
              </p>
            </div>
          </Card>

          <div className="mt-5 flex items-center justify-center gap-5 text-slate-200/55">
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
