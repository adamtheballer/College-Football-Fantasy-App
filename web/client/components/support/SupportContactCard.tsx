import { useState } from "react";
import { Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useRuntimeCapabilities } from "@/components/RuntimeCompatibilityGate";

/**
 * The app's only bug-report workflow: open a pre-addressed email to support.
 * Keeping it shared prevents Settings and the dedicated route from drifting.
 */
export function SupportContactCard() {
  const { support_email: supportEmail } = useRuntimeCapabilities();
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">(
    "idle",
  );

  if (!supportEmail) return null;

  const reportBugMailto = `mailto:${supportEmail}?subject=${encodeURIComponent(
    "College Football Fantasy bug report",
  )}`;

  const copySupportEmail = async () => {
    try {
      await navigator.clipboard.writeText(supportEmail);
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  };

  return (
    <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5">
      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-primary">
        Email Support
      </p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Email us with the page, what happened, and the steps that led to the
        issue.
      </p>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <a
          href={`mailto:${supportEmail}`}
          className="break-all text-sm font-black text-foreground underline decoration-primary/50 underline-offset-4 transition hover:text-primary"
        >
          {supportEmail}
        </a>
        <Button
          type="button"
          variant="outline"
          onClick={() => void copySupportEmail()}
          className="shrink-0 rounded-xl border-primary/25 text-[10px] font-black uppercase tracking-[0.16em]"
          aria-live="polite"
        >
          <Copy className="mr-2 h-3.5 w-3.5" />
          {copyState === "copied"
            ? "Copied"
            : copyState === "error"
              ? "Copy Failed"
              : "Copy Email"}
        </Button>
      </div>
      <a
        href={reportBugMailto}
        className="mt-4 inline-flex min-h-10 items-center rounded-xl border border-cfb-danger/35 bg-cfb-danger/10 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-red-100 transition hover:border-cfb-danger/60 hover:bg-cfb-danger/20"
      >
        Report a Bug
      </a>
    </div>
  );
}
