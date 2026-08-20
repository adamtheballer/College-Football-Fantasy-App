import { Swords } from "lucide-react";

import { useLeagueRivalry, useRivalryActions } from "@/hooks/use-leagues";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";

export function RivalryControls({ leagueId }: { leagueId: number }) {
  const rivalry = useLeagueRivalry(leagueId);
  const actions = useRivalryActions(leagueId);
  const data = rivalry.data;
  if (rivalry.isLoading || !data?.eligible) return null;
  if (data.rivalry) return <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.13em] text-amber-200"><Swords className="h-3.5 w-3.5" /> Permanent rival: {data.rivalry.opponent_team_name}</p>;
  if (data.outgoing_invite) return <button type="button" onClick={() => actions.cancel.mutate(data.outgoing_invite!.id)} disabled={actions.cancel.isPending} className="text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-secondary underline underline-offset-4">Cancel rivalry invite</button>;
  if (data.incoming_invites.length) return <div className="flex flex-wrap items-center gap-2" aria-label="Rivalry invitations">{data.incoming_invites.map((invite) => <div key={invite.id} className="flex items-center gap-2 rounded-lg border border-amber-300/30 bg-amber-300/[0.06] px-2 py-1.5"><ManagerAvatar avatarUrl={invite.sender_manager_avatar_url} managerName={invite.sender_manager_name} size="xs" /><span className="text-[10px] font-black text-cfb-text-primary">{invite.sender_team_name}</span><button type="button" onClick={() => actions.accept.mutate(invite.id)} className="text-[10px] font-black uppercase text-emerald-300">Accept</button><button type="button" onClick={() => actions.decline.mutate(invite.id)} className="text-[10px] font-black uppercase text-cfb-text-muted">Decline</button></div>)}</div>;
  if (!data.candidates.length) return null;
  return <details className="text-left"><summary className="cursor-pointer list-none text-[10px] font-black uppercase tracking-[0.13em] text-amber-200"><span className="inline-flex items-center gap-2"><Swords className="h-3.5 w-3.5" /> Choose permanent rival</span></summary><div className="mt-2 flex max-h-44 flex-col gap-1 overflow-y-auto">{data.candidates.map((candidate) => <button key={candidate.team_id} type="button" onClick={() => actions.invite.mutate(candidate.team_id)} disabled={actions.invite.isPending} className="flex items-center gap-2 rounded-lg border border-cfb-border-subtle bg-cfb-surface px-2 py-2 text-left hover:bg-cfb-surface-hover"><ManagerAvatar avatarUrl={candidate.manager_avatar_url} managerName={candidate.manager_name} size="xs" /><span className="min-w-0 flex-1 truncate text-[11px] font-bold text-cfb-text-primary">{candidate.team_name}</span><span className="text-[10px] font-black uppercase text-cfb-brand">Invite</span></button>)}</div></details>;
}
