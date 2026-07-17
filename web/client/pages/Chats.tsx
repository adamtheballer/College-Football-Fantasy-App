import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRightLeft, ChevronUp, CircleAlert, LoaderCircle, MessageCircleMore, MessageSquare, Plus, RefreshCw, RotateCcw, Send, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  useChatMessages,
  useChatMessageUpdates,
  useCreateDirectChatThread,
  useLeagueChatThreads,
  useMarkChatThreadRead,
  useSendChatMessage,
} from "@/hooks/use-chat";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import { useLeagues } from "@/hooks/use-leagues";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatMessage, ChatThread } from "@/types/chat";

const formatTime = (value: string) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown time";
  return parsed.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

const dateLabel = (value: string) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Earlier";
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (parsed.toDateString() === today.toDateString()) return "Today";
  if (parsed.toDateString() === yesterday.toDateString()) return "Yesterday";
  return parsed.toLocaleDateString([], { month: "long", day: "numeric", year: parsed.getFullYear() === today.getFullYear() ? undefined : "numeric" });
};

const sameDay = (left: string, right: string) => new Date(left).toDateString() === new Date(right).toDateString();

const initials = (value: string) => value.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "M";

const errorMessage = (error: unknown) =>
  error instanceof ApiError ? error.message : "Chat could not be loaded. Please try again.";

const createClientMessageId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`;

function threadLabel(thread: ChatThread, currentUserId?: number) {
  if (thread.thread_type === "league") return `# ${thread.title || "General"}`;
  const otherParticipant = thread.participants.find((participant) => participant.user_id !== currentUserId);
  return otherParticipant ? `Direct message · ${otherParticipant.display_name}` : "Direct message";
}

type TradeAsset = {
  player_id: number | null;
  name: string;
  position: string | null;
  school: string | null;
};

const isRecord = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && !Array.isArray(value);

const tradeAssets = (value: unknown): TradeAsset[] =>
  Array.isArray(value)
    ? value.flatMap((asset) => {
      if (!isRecord(asset) || typeof asset.name !== "string") return [];
      return [{
        player_id: typeof asset.player_id === "number" ? asset.player_id : null,
        name: asset.name,
        position: typeof asset.position === "string" ? asset.position : null,
        school: typeof asset.school === "string" ? asset.school : null,
      }];
    })
    : [];

export function TradeFinalizedCard({ message }: { message: { league_id: number; body: string | null; metadata: Record<string, unknown> } }) {
  const metadata = message.metadata;
  const proposingTeam = isRecord(metadata.proposing_team) && typeof metadata.proposing_team.name === "string"
    ? metadata.proposing_team.name
    : "Proposing team";
  const receivingTeam = isRecord(metadata.receiving_team) && typeof metadata.receiving_team.name === "string"
    ? metadata.receiving_team.name
    : "Receiving team";
  const proposingSends = tradeAssets(metadata.proposing_team_sends);
  const receivingSends = tradeAssets(metadata.receiving_team_sends);
  const processingStatus = metadata.processing_status === "processed" ? "processed" : "pending_transfer";
  const processAt = typeof metadata.players_process_at === "string" ? metadata.players_process_at : null;
  const tradeId = typeof metadata.trade_id === "number" ? metadata.trade_id : null;
  const playerList = (assets: TradeAsset[]) => assets.length
    ? assets.map((asset) => <li key={`${asset.player_id ?? asset.name}-${asset.position ?? ""}`}>{asset.name}{asset.position ? ` · ${asset.position}` : ""}{asset.school ? ` · ${asset.school}` : ""}</li>)
    : <li>No players listed</li>;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-cfb-gold">
        <ArrowRightLeft className="h-4 w-4" /> Trade Finalized
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-black/15 p-3">
          <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground">{proposingTeam} receives</p>
          <ul className="mt-2 space-y-1 text-sm font-semibold text-foreground">{playerList(receivingSends)}</ul>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/15 p-3">
          <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground">{receivingTeam} receives</p>
          <ul className="mt-2 space-y-1 text-sm font-semibold text-foreground">{playerList(proposingSends)}</ul>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">
        <span>{processingStatus === "processed" ? "Roster transfer complete" : processAt ? `Roster transfer pending · Players process ${formatTime(processAt)}` : "Roster transfer pending"}</span>
        {tradeId ? <a href={`/leagues/${message.league_id}/trades/${tradeId}`} className="rounded-lg border border-primary/50 bg-primary/10 px-3 py-2 text-primary transition hover:bg-primary/20">View trade</a> : null}
      </div>
    </div>
  );
}

export default function Chats() {
  const { user } = useAuth();
  const { data: leagues = [], isLoading: leaguesLoading } = useLeagues(50, Boolean(user));
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const [selectedLeagueId, setSelectedLeagueId] = useState<number | null>(activeLeagueId);
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [activeThreadByLeague, setActiveThreadByLeague] = useState<Record<number, number>>({});
  const [isNewMessageOpen, setIsNewMessageOpen] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");
  const [olderCursor, setOlderCursor] = useState<number | null>(null);
  const [olderMessages, setOlderMessages] = useState<ChatMessage[]>([]);
  const lastMarkedMessageId = useRef<number | null>(null);
  const loadedOlderPageKeys = useRef(new Set<string>());

  useEffect(() => {
    if (!leagues.length) {
      setSelectedLeagueId(null);
      return;
    }
    setSelectedLeagueId((current) => {
      if (current && leagues.some((league) => league.id === current)) return current;
      if (activeLeagueId && leagues.some((league) => league.id === activeLeagueId)) return activeLeagueId;
      return leagues[0].id;
    });
  }, [activeLeagueId, leagues]);

  useEffect(() => {
    if (selectedLeagueId && selectedLeagueId !== activeLeagueId) setActiveLeagueId(selectedLeagueId);
  }, [activeLeagueId, selectedLeagueId, setActiveLeagueId]);

  const selectedLeague = useMemo(
    () => leagues.find((league) => league.id === selectedLeagueId) ?? null,
    [leagues, selectedLeagueId],
  );
  const chatThreads = useLeagueChatThreads(selectedLeagueId ?? undefined, Boolean(selectedLeagueId));
  const threads = chatThreads.data?.data ?? [];

  useEffect(() => {
    const masterThread = threads.find((thread) => thread.thread_type === "league");
    setSelectedThreadId((current) => {
      if (current && threads.some((thread) => thread.id === current)) return current;
      const savedThreadId = selectedLeagueId ? activeThreadByLeague[selectedLeagueId] : null;
      if (savedThreadId && threads.some((thread) => thread.id === savedThreadId)) return savedThreadId;
      return masterThread?.id ?? threads[0]?.id ?? null;
    });
    lastMarkedMessageId.current = null;
  }, [activeThreadByLeague, selectedLeagueId, threads]);

  useEffect(() => {
    if (!selectedLeagueId || !selectedThreadId) return;
    setActiveThreadByLeague((current) => current[selectedLeagueId] === selectedThreadId
      ? current
      : { ...current, [selectedLeagueId]: selectedThreadId });
  }, [selectedLeagueId, selectedThreadId]);

  const selectedThread = threads.find((thread) => thread.id === selectedThreadId) ?? null;
  const messages = useChatMessages(selectedLeagueId ?? undefined, selectedThreadId ?? undefined, undefined, undefined, Boolean(selectedThreadId));
  const olderMessagePage = useChatMessages(selectedLeagueId ?? undefined, selectedThreadId ?? undefined, olderCursor ?? undefined, undefined, Boolean(selectedThreadId && olderCursor));
  const sendMessage = useSendChatMessage(selectedLeagueId ?? undefined, selectedThreadId ?? undefined);
  const markThreadRead = useMarkChatThreadRead(selectedLeagueId ?? undefined, selectedThreadId ?? undefined);
  const createDirectThread = useCreateDirectChatThread(selectedLeagueId ?? undefined);
  const messageRows = messages.data?.data ?? [];

  useEffect(() => {
    setOlderCursor(null);
    setOlderMessages([]);
    loadedOlderPageKeys.current.clear();
  }, [selectedLeagueId, selectedThreadId]);

  useEffect(() => {
    if (!olderCursor || !olderMessagePage.data || !selectedLeagueId || !selectedThreadId) return;
    const pageKey = `${selectedLeagueId}:${selectedThreadId}:${olderCursor}`;
    if (loadedOlderPageKeys.current.has(pageKey)) return;
    loadedOlderPageKeys.current.add(pageKey);
    setOlderMessages((current) => {
      const knownIds = new Set(current.map((message) => message.id));
      return [...olderMessagePage.data.data.filter((message) => !knownIds.has(message.id)), ...current];
    });
  }, [olderCursor, olderMessagePage.data, selectedLeagueId, selectedThreadId]);

  const allMessages = useMemo(() => {
    const byId = new Map<number, ChatMessage>();
    [...olderMessages, ...messageRows].forEach((message) => byId.set(message.id, message));
    return [...byId.values()].sort((left, right) => {
      const timeDifference = new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
      return timeDifference || left.id - right.id;
    });
  }, [messageRows, olderMessages]);

  const lastKnownMessageId = allMessages.reduce(
    (latestId, message) => message.id > latestId ? message.id : latestId,
    0,
  );
  const messageUpdates = useChatMessageUpdates(
    selectedLeagueId ?? undefined,
    selectedThreadId ?? undefined,
    lastKnownMessageId,
    Boolean(selectedThreadId),
  );

  useEffect(() => {
    const latestMessage = [...allMessages].reverse().find((message) => message.id > 0);
    if (!latestMessage || latestMessage.id === lastMarkedMessageId.current || markThreadRead.isPending) return;
    markThreadRead.mutate(latestMessage.id, {
      onSuccess: () => {
        lastMarkedMessageId.current = latestMessage.id;
      },
    });
  }, [allMessages, markThreadRead]);

  const masterThread = threads.find((thread) => thread.thread_type === "league");
  const managerOptions = (masterThread?.participants ?? []).filter((member) => member.user_id !== user?.id);
  const selectedThreadType = selectedThread?.thread_type === "league" ? "League chat" : "Direct message";
  const directParticipant = selectedThread?.thread_type === "direct"
    ? selectedThread.participants.find((participant) => participant.user_id !== user?.id)
    : null;
  const isSystemMessage = (messageType: string) => messageType !== "user";

  const sendDraftMessage = () => {
    const body = draftMessage.trim();
    if (!body || !selectedThreadId || sendMessage.isPending) return;
    sendMessage.mutate({ body, client_message_id: createClientMessageId() });
    setDraftMessage("");
  };

  const handleSend = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    sendDraftMessage();
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendDraftMessage();
    }
  };

  const handleCreateDirectThread = (recipientUserId: number) => {
    if (createDirectThread.isPending) return;
    createDirectThread.mutate(recipientUserId, {
      onSuccess: (thread) => {
        setSelectedThreadId(thread.id);
        setIsNewMessageOpen(false);
      },
    });
  };

  const handleRetry = (message: ChatMessage) => {
    if (!message.body || !message.client_message_id || sendMessage.isPending) return;
    sendMessage.mutate({
      body: message.body,
      client_message_id: message.client_message_id,
      reply_to_message_id: message.reply_to_message_id ?? undefined,
    });
  };

  const oldestMessageId = allMessages.find((message) => message.id > 0)?.id ?? null;
  const canLoadOlder = Boolean(messages.data?.next_before_message_id || olderMessagePage.data?.next_before_message_id);
  const handleLoadOlder = () => {
    if (oldestMessageId && !olderMessagePage.isFetching) setOlderCursor(oldestMessageId);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-5 pb-24 pt-6 lg:pb-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-5xl font-black uppercase italic tracking-tighter text-transparent">League Chat</h1>
          <p className="text-[10px] font-black uppercase tracking-[0.28em] text-muted-foreground/70">League conversation, manager messages, and binding events</p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground">
          <RefreshCw className={cn("h-3.5 w-3.5 text-primary", (chatThreads.isFetching || messageUpdates.isFetching) && "animate-spin")} /> Live updates
        </div>
      </div>

      <Card className="rounded-[1.75rem] border border-white/10 bg-card/45">
        <CardContent className="grid gap-3 p-4 md:grid-cols-[minmax(260px,1fr)_auto] md:items-end">
          <div className="space-y-2">
            <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground/60">Selected league</p>
            <Select value={selectedLeagueId ? String(selectedLeagueId) : ""} onValueChange={(value) => setSelectedLeagueId(Number(value))}>
              <SelectTrigger className="h-12 rounded-xl border-white/10 bg-white/[0.03] text-[11px] font-black uppercase tracking-[0.12em]">
                <SelectValue placeholder={leaguesLoading ? "Loading leagues..." : "Select league"} />
              </SelectTrigger>
              <SelectContent>{leagues.map((league) => <SelectItem key={league.id} value={String(league.id)}>{league.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-center text-[10px] font-black uppercase tracking-[0.14em] text-red-100">
            {threads.reduce((total, thread) => total + thread.unread_count, 0)} unread in this league
          </div>
        </CardContent>
      </Card>

      {!selectedLeagueId ? (
        <Card className="rounded-[2rem] border border-white/10 bg-card/40"><CardContent className="p-8 text-sm text-muted-foreground">Join or create a league to start chatting.</CardContent></Card>
      ) : chatThreads.isError ? (
        <Card className="rounded-[2rem] border border-red-400/40 bg-red-950/20"><CardContent className="p-8 text-sm text-red-100">{errorMessage(chatThreads.error)}</CardContent></Card>
      ) : (
        <div className="grid min-h-[680px] gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
          <Card className="overflow-hidden rounded-[1.75rem] border border-white/10 bg-card/45">
            <CardHeader className="flex-row items-center justify-between border-b border-white/10 px-5 py-4">
              <CardTitle className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.22em] text-primary"><Users className="h-4 w-4" />Threads</CardTitle>
              <button type="button" onClick={() => setIsNewMessageOpen((open) => !open)} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-primary/50 bg-primary/10 px-2.5 text-[9px] font-black uppercase tracking-[0.12em] text-primary hover:bg-primary/20"><Plus className="h-3.5 w-3.5" />New message</button>
            </CardHeader>
            <CardContent className="space-y-4 p-3">
              {isNewMessageOpen ? (
                <div className="rounded-xl border border-primary/30 bg-primary/[0.06] p-3">
                  <p className="mb-2 text-[9px] font-black uppercase tracking-[0.16em] text-primary">Message a league manager</p>
                  <div className="max-h-56 space-y-1 overflow-y-auto">
                    {managerOptions.map((member) => <button key={member.user_id} type="button" onClick={() => handleCreateDirectThread(member.user_id)} disabled={createDirectThread.isPending} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-white/[0.06] disabled:opacity-50"><span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-[9px] font-black text-primary">{initials(member.display_name)}</span><span className="min-w-0"><span className="block truncate text-xs font-bold text-foreground">{member.display_name}</span><span className="block truncate text-[10px] text-muted-foreground">{member.fantasy_team_name ?? "League manager"}</span></span></button>)}
                    {!managerOptions.length ? <p className="px-2 py-3 text-xs text-muted-foreground">No other active managers yet.</p> : null}
                  </div>
                  {createDirectThread.isError ? <p className="mt-2 text-xs text-red-200">{errorMessage(createDirectThread.error)}</p> : null}
                </div>
              ) : null}

              {chatThreads.isLoading ? <p className="px-2 py-4 text-xs text-muted-foreground">Loading threads…</p> : null}
              <div className="space-y-1">
                {threads.map((thread) => {
                  const participant = thread.other_participant;
                  const title = thread.thread_type === "league" ? `# ${thread.title || "General"}` : participant?.display_name ?? "Direct message";
                  const preview = thread.last_message_preview ?? (thread.thread_type === "league" ? "All current league members" : participant?.fantasy_team_name ?? "Private league conversation");
                  return <button key={thread.id} type="button" onClick={() => { setSelectedThreadId(thread.id); lastMarkedMessageId.current = null; }} className={cn("flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition", selectedThreadId === thread.id ? "border-primary/60 bg-primary/10" : "border-transparent hover:border-white/10 hover:bg-white/[0.035]")}>
                    <span className={cn("inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[10px] font-black", thread.thread_type === "league" ? "bg-primary/15 text-primary" : "bg-white/[0.08] text-foreground")}>{thread.thread_type === "league" ? "#" : initials(participant?.display_name ?? "DM")}</span>
                    <span className="min-w-0 flex-1"><span className="block truncate text-xs font-black text-foreground">{title}</span><span className="mt-0.5 block truncate text-[10px] text-muted-foreground">{preview}</span></span>
                    <span className="flex shrink-0 flex-col items-end gap-1">{thread.last_message_at ? <span className="text-[8px] font-bold text-muted-foreground">{formatTime(thread.last_message_at)}</span> : null}{thread.unread_count > 0 ? <span className="inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[9px] font-black text-white">{thread.unread_count > 99 ? "99+" : thread.unread_count}</span> : null}</span>
                  </button>;
                })}
              </div>
            </CardContent>
          </Card>

          <Card className="flex min-h-[680px] flex-col overflow-hidden rounded-[1.75rem] border border-white/10 bg-card/45">
            <CardHeader className="border-b border-white/10 px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary"><MessageCircleMore className="h-5 w-5" /></span>
                <div className="min-w-0"><CardTitle className="truncate text-sm font-black uppercase tracking-[0.16em] text-foreground">{selectedThread ? threadLabel(selectedThread, user?.id) : "Select a thread"}</CardTitle>{selectedThread && selectedLeague ? <p className="mt-1 truncate text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">{selectedLeague.name} · {selectedThreadType}{directParticipant ? ` · ${directParticipant.fantasy_team_name ?? directParticipant.display_name}` : ""}</p> : null}</div>
              </div>
            </CardHeader>
            <CardContent className="flex min-h-0 flex-1 flex-col p-0">
              <div className="flex-1 space-y-3 overflow-y-auto p-5">
                {canLoadOlder ? <div className="flex justify-center"><button type="button" onClick={handleLoadOlder} disabled={olderMessagePage.isFetching} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground disabled:opacity-50">{olderMessagePage.isFetching ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <ChevronUp className="h-3.5 w-3.5" />}Load older messages</button></div> : null}
                {messages.isLoading ? <p className="py-12 text-center text-xs text-muted-foreground">Loading messages…</p> : null}
                {messages.isError ? <p className="rounded-xl border border-red-400/40 bg-red-950/20 p-4 text-sm text-red-100">{errorMessage(messages.error)}</p> : null}
                {!messages.isLoading && !messages.isError && allMessages.length === 0 ? <div className="py-20 text-center"><MessageSquare className="mx-auto h-8 w-8 text-primary/60" /><p className="mt-3 text-sm font-semibold text-foreground">No messages yet</p><p className="mt-1 text-xs text-muted-foreground">Start the conversation with your league.</p></div> : null}
                {allMessages.map((message, index) => <div key={message.id} className="space-y-3">
                  {index === 0 || !sameDay(allMessages[index - 1].created_at, message.created_at) ? <div className="flex items-center gap-3 py-2"><span className="h-px flex-1 bg-white/10" /><span className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">{dateLabel(message.created_at)}</span><span className="h-px flex-1 bg-white/10" /></div> : null}
                  <div className={cn("max-w-[88%] rounded-2xl border px-4 py-3", isSystemMessage(message.message_type) ? "mx-auto max-w-[96%] border-cfb-gold/30 bg-cfb-gold/10" : message.sender_user_id === user?.id ? "ml-auto border-primary/40 bg-primary/15" : "border-white/10 bg-white/[0.04]")}>
                    <div className="flex items-center justify-between gap-4 text-[9px] font-black uppercase tracking-[0.13em] text-muted-foreground/70"><span>{isSystemMessage(message.message_type) ? message.message_type.replace("_", " ") : message.sender_user_id === user?.id ? "You" : message.sender_display_name ?? `Manager #${message.sender_user_id}`}{message.sender_fantasy_team_name ? ` · ${message.sender_fantasy_team_name}` : ""}</span><span>{formatTime(message.created_at)}</span></div>
                    {message.message_type === "trade_finalized" ? <div className="mt-2"><TradeFinalizedCard message={message} /></div> : message.deleted_at ? <p className="mt-2 text-sm italic text-muted-foreground">Message deleted</p> : message.body ? <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground">{message.body}</p> : null}
                    {message.delivery_status === "sending" ? <p className="mt-2 flex items-center gap-1 text-[9px] font-black uppercase tracking-[0.12em] text-primary"><LoaderCircle className="h-3 w-3 animate-spin" />Sending</p> : null}
                    {message.delivery_status === "failed" ? <div className="mt-2 flex items-center justify-between gap-2 text-[9px] font-black uppercase tracking-[0.12em] text-red-200"><span className="flex items-center gap-1"><CircleAlert className="h-3 w-3" />Failed to send</span><button type="button" onClick={() => handleRetry(message)} className="inline-flex items-center gap-1 rounded-md border border-red-300/40 px-2 py-1 hover:bg-red-500/10"><RotateCcw className="h-3 w-3" />Retry</button></div> : null}
                  </div>
                </div>)}
              </div>
              <form onSubmit={handleSend} className="border-t border-white/10 bg-black/10 p-4">
                {sendMessage.isError ? <p className="mb-3 rounded-xl border border-red-400/40 bg-red-950/20 px-3 py-2 text-xs text-red-100">{errorMessage(sendMessage.error)}</p> : null}
                <div className="flex gap-3"><textarea value={draftMessage} onChange={(event) => setDraftMessage(event.target.value)} onKeyDown={handleComposerKeyDown} disabled={!selectedThread} maxLength={2000} placeholder={selectedThread ? "Message your league…" : "Select a thread first"} className="min-h-14 flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary/60 disabled:opacity-50" /><button type="submit" disabled={!draftMessage.trim() || !selectedThread || sendMessage.isPending} className="inline-flex h-14 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-[10px] font-black uppercase tracking-[0.16em] text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"><Send className="h-4 w-4" />Send</button></div>
                <div className="mt-2 flex justify-between text-[9px] font-bold uppercase tracking-[0.12em] text-muted-foreground"><span>Enter to send · Shift+Enter for a new line</span><span className={cn(draftMessage.length >= 1800 && "text-cfb-gold")}>{draftMessage.length}/2000</span></div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
