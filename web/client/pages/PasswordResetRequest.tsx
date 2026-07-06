import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Mail, ShieldCheck, Trophy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";

export default function PasswordResetRequest() {
  const { requestPasswordReset } = useAuth();
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await requestPasswordReset(email);
      setMessage("If that email exists, a reset link has been sent. Check your inbox.");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setError(detail || "Could not request password reset. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative flex h-full max-h-full items-center justify-center overflow-hidden rounded-[2rem] border border-white/10 bg-[#06111f] p-4 shadow-[0_0_80px_rgba(14,165,233,0.18)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(34,211,238,0.34),transparent_34%),radial-gradient(circle_at_84%_18%,rgba(251,191,36,0.24),transparent_28%),linear-gradient(135deg,rgba(15,23,42,0.15),rgba(2,6,23,0.88))]" />
      <div className="absolute inset-0 opacity-[0.16] [background-image:linear-gradient(rgba(255,255,255,0.16)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.16)_1px,transparent_1px)] [background-size:48px_48px]" />

      <Card className="relative w-full max-w-[480px] overflow-hidden rounded-[1.75rem] border border-white/15 bg-slate-950/78 shadow-[0_28px_80px_rgba(0,0,0,0.42)] backdrop-blur-2xl">
        <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-cyan-300 via-amber-200 to-rose-400" />
        <CardContent className="relative space-y-6 p-6 sm:p-8">
          <div className="space-y-3 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-200 via-cyan-300 to-blue-500 shadow-[0_0_38px_rgba(34,211,238,0.34)]">
              <Trophy className="h-6 w-6 text-slate-950" />
            </div>
            <div>
              <h1 className="text-3xl font-black uppercase italic tracking-tight text-white">Reset Password</h1>
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100/60">
                We’ll send a secure reset link if the account exists.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="ml-3 text-[10px] font-black uppercase tracking-widest text-cyan-100/70">Email Address</label>
              <div className="group relative">
                <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/45 transition-colors group-focus-within:text-cyan-200" />
                <Input
                  type="email"
                  placeholder="coach@saturday.com"
                  className="h-12 rounded-2xl border-cyan-200/10 bg-white/10 pl-12 text-sm font-bold text-white placeholder:text-slate-300/40 transition-all focus:border-cyan-200/50 focus:ring-cyan-300/25"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
            </div>

            {message && (
              <div className="rounded-2xl border border-emerald-200/35 bg-emerald-300/12 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-100">
                {message}
              </div>
            )}
            {error && (
              <div className="rounded-2xl border border-red-300/35 bg-red-500/15 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-red-100">
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="h-12 w-full rounded-2xl bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-[10px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_18px_42px_rgba(14,165,233,0.32)] transition-all hover:brightness-110"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Sending..." : "Send Reset Link"}
            </Button>
          </form>

          <div className="flex items-center justify-between border-t border-white/10 pt-4 text-[10px] font-black uppercase tracking-widest text-slate-300/70">
            <Link to="/login" className="inline-flex items-center gap-2 text-cyan-100/75 hover:text-cyan-100">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Sign In
            </Link>
            <span className="inline-flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-200" />
              Secure Reset
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
