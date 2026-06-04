import { CheckCircle2, Copy, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { copyInviteLinkToClipboard, getInviteLinkStatus } from "@/lib/url";

type MockDraftInviteLinkPanelProps = {
  inviteLink: string;
  inviteCode?: string;
  title?: string;
};

export function MockDraftInviteLinkPanel({
  inviteLink,
  inviteCode,
  title = "Invite Link",
}: MockDraftInviteLinkPanelProps) {
  const status = getInviteLinkStatus(inviteLink);

  return (
    <div className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-100">{title}</p>
          <div
            className={`mt-2 inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
              status.isLocalOnly
                ? "border-amber-300/30 bg-amber-400/10 text-amber-100"
                : "border-emerald-300/30 bg-emerald-400/10 text-emerald-100"
            }`}
          >
            {status.isLocalOnly ? <TriangleAlert className="mr-2 h-3 w-3" /> : <CheckCircle2 className="mr-2 h-3 w-3" />}
            {status.label}
          </div>
        </div>
        <Button variant="outline" onClick={() => void copyInviteLinkToClipboard(inviteLink)}>
          <Copy className="mr-2 h-4 w-4" />
          Copy Invite Link
        </Button>
      </div>
      <p className="mt-3 truncate rounded-xl bg-slate-950/60 px-4 py-2 text-sm font-bold text-slate-100">
        {inviteLink}
      </p>
      {inviteCode ? (
        <p className="mt-2 break-all text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">
          Token: {inviteCode}
        </p>
      ) : null}
      {status.warning ? <p className="mt-3 text-sm font-semibold leading-6 text-amber-100">{status.warning}</p> : null}
    </div>
  );
}
