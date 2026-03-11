import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { setPendingGuide } from "@/lib/onboarding";
import {
  Trophy,
  Mail,
  Lock,
  ArrowRight,
  Github,
  Chrome,
  Apple,
  Zap,
  ShieldCheck
} from "lucide-react";

export default function Login() {
  const navigate = useNavigate();
  const { login, isLoggedIn } = useAuth();

  useEffect(() => {
    if (isLoggedIn) {
      navigate("/", { replace: true });
    }
  }, [isLoggedIn, navigate]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await login(email, password);
      let parsedUser: { id: number } | null = null;
      try {
        const savedUser = localStorage.getItem("cfb_user");
        parsedUser = savedUser ? (JSON.parse(savedUser) as { id: number }) : null;
      } catch {
        parsedUser = null;
      }
      if (parsedUser) {
        setPendingGuide(parsedUser.id);
      }
      navigate("/", { replace: true });
    } catch {
      setError("Sign in failed. Check email/password and try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-6 relative overflow-hidden">
      <div className="w-full max-w-[450px] space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-1000">
        <div className="flex flex-col items-center text-center space-y-4">
          <Link to="/" className="group flex items-center gap-2 mb-4 hover:opacity-80 transition-opacity">
            <div className="p-3 rounded-2xl bg-primary shadow-[0_0_25px_rgba(var(--primary),0.4)] group-hover:scale-110 transition-transform duration-500">
              <Trophy className="w-6 h-6 text-primary-foreground" />
            </div>
          </Link>
          <div className="space-y-1">
            <h1 className="text-3xl font-black italic tracking-tighter text-foreground uppercase leading-none">
              Welcome Back
            </h1>
            <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground uppercase opacity-60">
              Enter your credentials to access your leagues
            </p>
          </div>
        </div>

        <Card className="bg-card/40 backdrop-blur-xl border-border/60 rounded-[2.5rem] overflow-hidden shadow-2xl relative border-t-primary/20">
          <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
          <CardContent className="p-10 space-y-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60 ml-4">Email Address</label>
                  <div className="relative group">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/40 group-focus-within:text-primary transition-colors" />
                    <Input
                      type="email"
                      placeholder="coach@saturday.com"
                      className="bg-white/5 border-border/40 h-14 pl-12 rounded-2xl focus:ring-primary focus:border-primary transition-all text-sm font-medium"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center px-4">
                    <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60">Password</label>
                    <button type="button" className="text-[9px] font-black uppercase tracking-widest text-primary/60 hover:text-primary transition-colors">Forgot?</button>
                  </div>
                  <div className="relative group">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/40 group-focus-within:text-primary transition-colors" />
                    <Input 
                      type="password" 
                      placeholder="••••••••" 
                      className="bg-white/5 border-border/40 h-14 pl-12 rounded-2xl focus:ring-primary focus:border-primary transition-all text-sm font-medium"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>

              {error && (
                <div className="rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-[10px] font-bold uppercase tracking-[0.12em] text-red-300">
                  {error}
                </div>
              )}

              <Button 
                type="submit" 
                className="w-full h-14 rounded-2xl bg-primary hover:bg-primary/90 text-[11px] font-black uppercase tracking-[0.2em] shadow-[0_10px_30px_rgba(var(--primary),0.3)] transition-all group overflow-hidden"
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                ) : (
                  <span className="flex items-center gap-2 group-hover:gap-4 transition-all">
                    Sign In to Dashboard <ArrowRight className="w-4 h-4" />
                  </span>
                )}
              </Button>
            </form>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-border/40" />
              </div>
              <div className="relative flex justify-center text-[9px] font-black uppercase tracking-widest">
                <span className="bg-[#05080a] px-4 text-muted-foreground/40">Or continue with</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <Button variant="outline" className="h-14 rounded-2xl border-border/40 bg-white/5 hover:bg-white/10 transition-all">
                <Chrome className="w-5 h-5" />
              </Button>
              <Button variant="outline" className="h-14 rounded-2xl border-border/40 bg-white/5 hover:bg-white/10 transition-all">
                <Apple className="w-5 h-5" />
              </Button>
              <Button variant="outline" className="h-14 rounded-2xl border-border/40 bg-white/5 hover:bg-white/10 transition-all">
                <Github className="w-5 h-5" />
              </Button>
            </div>
          </CardContent>
          <div className="bg-white/5 px-10 py-6 border-t border-border/40 text-center">
             <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
               Don't have an account? <Link to="/signup" className="text-primary hover:underline font-black ml-1">Create One</Link>
             </p>
          </div>
        </Card>

        <div className="flex items-center justify-center gap-8 opacity-40">
           <div className="flex items-center gap-2">
              <ShieldCheck className="w-3 h-3 text-primary" />
              <span className="text-[8px] font-black uppercase tracking-widest">Secure SSL</span>
           </div>
           <div className="flex items-center gap-2">
              <Zap className="w-3 h-3 text-primary" />
              <span className="text-[8px] font-black uppercase tracking-widest">Live Scoring</span>
           </div>
        </div>
      </div>
    </div>
  );
}
