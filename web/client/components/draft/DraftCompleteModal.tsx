import { Clipboard, Loader2, Mail, RotateCcw, Trophy } from "lucide-react";

import { Button } from "@/components/ui/button";

export function DraftCompleteModal({
  open,
  choiceMade,
  emailPending,
  exitPending,
  emailError,
  historyTextAvailable,
  onSendEmail,
  onSkipEmail,
  onCopyHistory,
  onReset,
  onExit,
}: {
  open: boolean;
  choiceMade: boolean;
  emailPending: boolean;
  exitPending: boolean;
  emailError?: string | null;
  historyTextAvailable: boolean;
  onSendEmail: () => void;
  onSkipEmail: () => void;
  onCopyHistory?: () => void;
  onReset?: () => void;
  onExit: () => void;
}) {
  if (!open && !choiceMade) return null;
  if (choiceMade) {
    return (
      <div data-testid="draft-complete-modal" className="rounded-[2rem] border border-emerald-300/20 bg-emerald-400/10 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-lg font-black text-foreground">Mock Draft Complete</p>
            <p className="text-sm font-semibold text-muted-foreground">Copy the history or exit back to the Draft tab.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            {onCopyHistory ? (
              <Button variant="outline" disabled={!historyTextAvailable} onClick={onCopyHistory}>
                <Clipboard className="mr-2 h-4 w-4" /> Copy History
              </Button>
            ) : null}
            {onReset ? (
              <Button variant="outline" onClick={onReset}>
                <RotateCcw className="mr-2 h-4 w-4" /> Restart Mock
              </Button>
            ) : null}
            <Button className="bg-cyan-300 text-slate-950" disabled={exitPending} onClick={onExit}>
              {exitPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null} Exit Mock Draft
            </Button>
          </div>
        </div>
      </div>
    );
  }
  if (!open) return null;
  return (
    <div data-testid="draft-complete-modal" className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-xl">
      <div className="w-full max-w-xl rounded-[2rem] border border-cyan-200/20 bg-[#07111f] p-6 text-center shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
        <Trophy className="mx-auto h-10 w-10 text-cyan-200" />
        <p className="mt-4 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-200">Draft Complete</p>
        <h2 className="mt-2 text-2xl font-black text-white">Want to send the draft history to your email?</h2>
        {emailError ? <p className="mt-3 text-sm font-semibold text-amber-200">{emailError}</p> : null}
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <Button variant="outline" onClick={onSkipEmail}>No thanks</Button>
          <Button className="bg-cyan-300 text-slate-950" disabled={emailPending} onClick={onSendEmail}>
            {emailPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mail className="mr-2 h-4 w-4" />} Send to my email
          </Button>
        </div>
      </div>
    </div>
  );
}
