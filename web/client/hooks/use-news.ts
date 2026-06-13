import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";

export type NewsCategory = "transfer" | "injury" | "depth_chart" | "coaching" | "eligibility" | "team_news" | "general";

export type NewsItem = {
  id: number;
  title: string;
  summary: string | null;
  category: string;
  source_name: string;
  source_url: string;
  published_at: string | null;
  player_id: number | null;
  player_name_raw: string | null;
  team_name_raw: string | null;
  canonical_team: string | null;
  position: string | null;
  confidence_score: number;
  fantasy_relevance_score: number;
  fantasy_impact: string | null;
  tags: string[];
  is_breaking: boolean;
};

export type NewsListResponse = {
  data: NewsItem[];
  total: number;
  limit: number;
  offset: number;
};

export type NewsFeedFilters = {
  category?: string;
  team?: string;
  player_id?: number;
  position?: string;
  limit?: number;
  offset?: number;
  min_relevance?: number;
  breaking_only?: boolean;
  categories?: string;
  sort?: "impact" | "recent";
};

export function useNewsFeed(filters: NewsFeedFilters = {}, enabled = true) {
  return useQuery({
    queryKey: ["news", "feed", filters],
    enabled,
    staleTime: 60_000,
    retry: 1,
    queryFn: () => apiGet<NewsListResponse>("/news/feed", filters),
  });
}

export function useBreakingNews() {
  return useNewsFeed({ limit: 5, min_relevance: 20, sort: "recent" });
}

export function useTransferNews() {
  return useNewsFeed({ category: "transfer", limit: 5, sort: "recent" });
}
