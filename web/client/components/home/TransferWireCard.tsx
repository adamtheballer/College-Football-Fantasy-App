import { ExternalLink, RefreshCw, RadioTower, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useNewsFeed, type NewsFeedFilters, type NewsItem } from "@/hooks/use-news";
import { cn } from "@/lib/utils";

type NewsTab = "breaking" | "transfer" | "injury" | "team_news";

export const TRANSFER_WIRE_EMPTY_MESSAGE = "No fantasy-relevant news yet. Run news sync or add a manual item.";
export const TRANSFER_WIRE_ERROR_MESSAGE = "Unable to load Transfer Wire.";

const tabFilters: Record<NewsTab, NewsFeedFilters> = {
  breaking: { limit: 5, min_relevance: 20, sort: "recent" },
  transfer: { limit: 5, category: "transfer", sort: "recent" },
  injury: { limit: 5, category: "injury", sort: "recent" },
  team_news: { limit: 5, categories: "team_news,depth_chart,coaching,eligibility", sort: "recent" },
};

export const formatNewsCategory = (category: string) => category.replace(/_/g, " ").toUpperCase();

export const getNewsImpactLabel = (score: number) => {
  if (score >= 80) return "High Impact";
  if (score >= 55) return "Watch List";
  return "Monitor";
};

export const formatNewsRelativeTime = (value: string | null) => {
  if (!value) return "Recently discovered";
  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) return "Recently discovered";
  const diffSeconds = Math.max(0, Math.floor((Date.now() - parsed) / 1000));
  if (diffSeconds < 60) return "Just now";
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
};

function NewsItemRow({ item }: { item: NewsItem }) {
  const metadata = [item.player_name_raw, item.canonical_team || item.team_name_raw, item.position].filter(Boolean).join(" • ");
  const impactLabel = getNewsImpactLabel(item.fantasy_relevance_score);
  return (
    <article className="group rounded-3xl border border-white/10 bg-slate-950/25 p-4 transition-all duration-300 hover:border-primary/30 hover:bg-white/[0.045]">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="rounded-full border border-cyan-300/25 bg-cyan-400/10 text-[9px] font-black uppercase tracking-[0.18em] text-cyan-100">
          {formatNewsCategory(item.category)}
        </Badge>
        <Badge
          className={cn(
            "rounded-full border text-[9px] font-black uppercase tracking-[0.18em]",
            item.fantasy_relevance_score >= 80
              ? "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"
              : "border-amber-300/25 bg-amber-400/10 text-amber-100"
          )}
        >
          {impactLabel}
        </Badge>
        {metadata ? <span className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">{metadata}</span> : null}
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
        <div className="space-y-2">
          <h3 className="text-base font-black leading-6 tracking-tight text-foreground">{item.title}</h3>
          {item.summary ? <p className="line-clamp-2 text-sm font-semibold leading-6 text-muted-foreground/80">{item.summary}</p> : null}
          <p className="text-sm font-bold leading-6 text-cyan-100/85">
            {item.fantasy_impact || "Monitor for fantasy relevance before changing rankings or lineups."}
          </p>
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
            {item.source_name} • {formatNewsRelativeTime(item.published_at)}
          </p>
        </div>
        <a
          href={item.source_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-10 items-center justify-center rounded-2xl border border-primary/25 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-primary transition-colors hover:bg-primary/10"
        >
          Read Source
          <ExternalLink className="ml-2 h-3.5 w-3.5" />
        </a>
      </div>
    </article>
  );
}

export function TransferWireCard() {
  const [activeTab, setActiveTab] = useState<NewsTab>("breaking");
  const filters = useMemo(() => tabFilters[activeTab], [activeTab]);
  const { data, isLoading, isError, refetch, isFetching } = useNewsFeed(filters);
  const items = data?.data ?? [];

  return (
    <Card className="relative overflow-hidden rounded-[2.75rem] border-cyan-200/10 bg-card/55">
      <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-cyan-300/14 blur-[80px]" />
      <div className="pointer-events-none absolute -bottom-20 left-0 h-56 w-72 rounded-full bg-emerald-300/10 blur-[90px]" />
      <CardHeader className="relative gap-5 border-b border-white/10 bg-white/[0.035] p-6 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-4 py-2">
            <RadioTower className="h-3.5 w-3.5 text-cyan-100" />
            <span className="text-[10px] font-black uppercase tracking-[0.28em] text-primary">CFB News Wire</span>
          </div>
          <div>
            <CardTitle className="text-3xl font-black italic uppercase tracking-tight text-foreground md:text-4xl">
              Transfer Wire
            </CardTitle>
            <p className="mt-2 max-w-2xl text-sm font-semibold leading-6 text-muted-foreground/85">
              Breaking movement, role changes, and fantasy-relevant college football news.
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          className="h-11 rounded-2xl border-primary/25 text-[10px] font-black uppercase tracking-[0.16em] text-primary"
          onClick={() => void refetch()}
          disabled={isFetching}
        >
          <RefreshCw className={cn("mr-2 h-4 w-4", isFetching ? "animate-spin" : "")} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="relative space-y-5 p-5 md:p-6">
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as NewsTab)}>
          <TabsList className="flex w-full flex-wrap justify-start gap-1 md:w-fit">
            <TabsTrigger value="breaking">Breaking</TabsTrigger>
            <TabsTrigger value="transfer">Transfers</TabsTrigger>
            <TabsTrigger value="injury">Injuries</TabsTrigger>
            <TabsTrigger value="team_news">Team News</TabsTrigger>
          </TabsList>
        </Tabs>
        {isLoading ? (
          <div className="flex min-h-40 items-center justify-center rounded-3xl border border-white/10 bg-slate-950/20 text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground">
            Loading Transfer Wire...
          </div>
        ) : isError ? (
          <div className="flex min-h-40 items-center justify-center rounded-3xl border border-red-300/20 bg-red-400/10 px-6 text-center text-sm font-black uppercase tracking-[0.2em] text-red-100">
            {TRANSFER_WIRE_ERROR_MESSAGE}
          </div>
        ) : items.length === 0 ? (
          <div className="flex min-h-40 flex-col items-center justify-center rounded-3xl border border-white/10 bg-slate-950/20 px-6 text-center">
            <Sparkles className="mb-3 h-6 w-6 text-primary" />
            <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground">
              {TRANSFER_WIRE_EMPTY_MESSAGE}
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            {items.slice(0, 5).map((item) => (
              <NewsItemRow key={item.id} item={item} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
