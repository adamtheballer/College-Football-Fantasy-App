import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { Mail, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SurfaceCard } from "@/components/fantasy";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

const GENERIC_SUCCESS = "If an account exists for that email, a reset link has been sent. The link expires in 30 minutes.";

export default function ForgotPassword() {
  const { requestPasswordReset } = useAuth();
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setState("error");
      setMessage("Enter a valid email address.");
      return;
    }
    setState("sending");
    setMessage(null);
    try {
      await requestPasswordReset(email);
      setState("sent");
      setMessage(GENERIC_SUCCESS);
    } catch (error) {
      setState("error");
      setMessage(error instanceof ApiError && error.status === 429 ? "Too many reset requests. Please wait before trying again." : "We could not send a reset request. Check your connection and retry.");
    }
  };

  return <main className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-xl items-center px-4 py-8 sm:px-6">
    <SurfaceCard variant="raised" padding="spacious" className="w-full">
      <div className="mb-7 text-center"><Mail className="mx-auto h-10 w-10 text-cfb-cyan" aria-hidden="true" /><p className="cfb-micro-label mt-4 text-cfb-brand">Account recovery</p><h1 className="mt-2 text-3xl font-black uppercase italic text-cfb-text-primary">Forgot your password?</h1><p className="mt-3 text-sm font-semibold leading-6 text-cfb-text-secondary">Enter the email connected to your College Football Fantasy account. We’ll send you a secure password-reset link.</p></div>
      {state === "sent" ? <div role="status" className="rounded-2xl border border-cfb-success/30 bg-cfb-success/10 p-5 text-sm font-semibold text-emerald-50"><p className="font-black uppercase tracking-wide">Check your email</p><p className="mt-2">{message}</p></div> : <form onSubmit={submit} className="space-y-5"><label className="block text-[10px] font-black uppercase tracking-widest text-cfb-text-muted" htmlFor="forgot-email">Email address<Input id="forgot-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 h-14 rounded-2xl text-base" required /></label>{message ? <p role="alert" className="text-sm font-semibold text-red-200">{message}</p> : null}<Button className="h-14 w-full rounded-2xl" disabled={state === "sending"}>{state === "sending" ? "Sending…" : <><Send className="mr-2 h-4 w-4" />Send reset email</>}</Button></form>}
      <Link to="/login" className="mt-6 block text-center text-xs font-black uppercase tracking-widest text-cfb-cyan hover:text-cyan-100">Back to sign in</Link>
    </SurfaceCard>
  </main>;
}
