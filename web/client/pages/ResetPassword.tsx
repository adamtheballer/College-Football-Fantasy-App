import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";

import { PasswordChangeForm } from "@/components/auth/PasswordChangeForm";
import { SurfaceCard } from "@/components/fantasy";
import { useRuntimeCapabilities } from "@/components/RuntimeCompatibilityGate";

export default function ResetPassword() {
  const navigate = useNavigate();
  const { email_enabled: emailEnabled, support_email: supportEmail } =
    useRuntimeCapabilities();

  if (!emailEnabled) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-xl items-center px-4 py-8 sm:px-6">
        <SurfaceCard
          variant="raised"
          padding="spacious"
          className="w-full text-center"
        >
          <p className="cfb-micro-label text-cfb-brand">Account security</p>
          <h1 className="mt-3 text-3xl font-black uppercase italic tracking-tight text-cfb-text-primary">
            Email unavailable during beta
          </h1>
          <p className="mt-4 text-sm font-semibold leading-6 text-cfb-text-secondary">
            Password-recovery email is not enabled for this beta. Sign in with
            your current password to change it from Settings.
          </p>
          {supportEmail ? (
            <a
              className="mt-5 inline-block text-sm font-bold text-cfb-gold hover:text-yellow-100"
              href={`mailto:${supportEmail}`}
            >
              Contact support
            </a>
          ) : null}
          <button
            type="button"
            className="mt-6 block w-full text-sm font-black uppercase tracking-widest text-cfb-cyan"
            onClick={() => navigate("/login")}
          >
            Back to sign in
          </button>
        </SurfaceCard>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-xl items-center px-4 py-8 sm:px-6">
      <SurfaceCard variant="raised" padding="spacious" className="w-full">
        <div className="mb-7 space-y-3 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-cfb-brand/15 text-cfb-cyan">
            <ShieldCheck className="h-7 w-7" aria-hidden="true" />
          </div>
          <p className="cfb-micro-label text-cfb-brand">Account security</p>
          <h1 className="text-3xl font-black uppercase italic tracking-tight text-cfb-text-primary">
            Reset Password
          </h1>
          <p className="text-sm font-semibold leading-6 text-cfb-text-secondary">
            To protect your account, enter your current password before choosing
            a new one.
          </p>
        </div>

        <PasswordChangeForm
          mode="reset"
          onCancel={() => navigate("/login")}
          onSuccess={() =>
            navigate("/login", {
              replace: true,
              state: { passwordResetSuccess: true },
            })
          }
        />

        <p className="mt-6 text-center text-sm font-medium text-cfb-text-secondary">
          Can&apos;t remember your current password? Contact support for account
          recovery.
          <Link
            to="/settings"
            className="ml-1 font-bold text-cfb-gold hover:text-yellow-100"
          >
            Support options
          </Link>
        </p>
      </SurfaceCard>
    </main>
  );
}
