import React, { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { setPendingGuide } from "@/lib/onboarding";
import { Trophy, Mail, Lock, User, ArrowRight } from "lucide-react";

export default function Signup() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signup, isLoggedIn } = useAuth();
  const redirectTarget =
    typeof location.state === "object" &&
    location.state &&
    "from" in location.state &&
    typeof location.state.from === "string"
      ? location.state.from
      : "/";
  const [firstName, setFirstName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoggedIn) {
      navigate(redirectTarget, { replace: true });
    }
  }, [isLoggedIn, navigate, redirectTarget]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const nextUser = await signup(firstName, email, password);
      if (nextUser) {
        setPendingGuide(nextUser.id);
      }
      navigate(redirectTarget, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (message.includes("409")) {
        setError("That email is already registered. Try signing in instead.");
      } else if (message.includes("Failed to fetch")) {
        setError("Cannot reach the server. Make sure backend is running on port 8000.");
      } else {
        setError("Create account failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-6">
      <div className="w-full max-w-[450px] space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-1000">
        <div className="flex flex-col items-center text-center space-y-4">
          <Link
            to="/"
            aria-label="Back to home"
            className="group flex items-center gap-2 mb-4 hover:opacity-80 transition-opacity"
          >
            <div className="p-3 rounded-2xl bg-primary shadow-[0_0_25px_rgba(var(--primary),0.4)] group-hover:scale-110 transition-transform duration-500">
              <Trophy className="w-6 h-6 text-primary-foreground" />
            </div>
          </Link>
          <div className="space-y-1">
            <h1 className="text-3xl font-black italic tracking-tighter text-foreground uppercase leading-none">
              Create Account
            </h1>
            <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground uppercase opacity-60">
              Start building your league
            </p>
          </div>
        </div>

        <Card className="bg-card/40 backdrop-blur-xl border-border/60 rounded-[2.5rem] overflow-hidden shadow-2xl">
          <CardContent className="p-10 space-y-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60 ml-4">First Name</label>
                  <div className="relative group">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/40 group-focus-within:text-primary transition-colors" />
                    <Input
                      type="text"
                      placeholder="Enter your first name"
                      className="bg-white/5 border-border/40 h-14 pl-12 rounded-2xl focus:ring-primary focus:border-primary transition-all text-sm font-medium"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      required
                    />
                  </div>
                </div>
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
                  <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60 ml-4">Password</label>
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
                    Create Account <ArrowRight className="w-4 h-4" />
                  </span>
                )}
              </Button>
            </form>
          </CardContent>
          <div className="bg-white/5 px-10 py-6 border-t border-border/40 text-center">
             <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
               Already have an account? <Link to="/login" className="text-primary hover:underline font-black ml-1">Sign In</Link>
             </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
