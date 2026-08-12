import { Bug } from "lucide-react";

import { SupportContactCard } from "@/components/support/SupportContactCard";
import { useRuntimeCapabilities } from "@/components/RuntimeCompatibilityGate";

/** A direct, refresh-safe destination for the sidebar Report Bug action. */
export default function ReportBug() {
  const { support_email: supportEmail } = useRuntimeCapabilities();
  return (
    <main className="mx-auto max-w-3xl space-y-8 pb-24 pt-10 sm:pt-14">
      <header className="border-b border-border/50 pb-8">
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-cfb-danger/30 bg-cfb-danger/10 text-red-100">
          <Bug className="h-5 w-5" aria-hidden="true" />
        </div>
        <p className="text-[10px] font-black uppercase tracking-[0.24em] text-primary">
          Beta feedback
        </p>
        <h1 className="mt-3 text-4xl font-black uppercase italic tracking-tight text-foreground sm:text-6xl">
          Report a Bug
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          {supportEmail
            ? "Send the product team the details by email. Your report opens in your email app, so nothing is silently lost inside the beta."
            : "Email feedback is unavailable during beta."}
        </p>
      </header>

      <SupportContactCard />
    </main>
  );
}
