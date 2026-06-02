import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import type { LeagueCreateResponse, LeagueDetail, LeagueListResponse } from "@/types/league";

export default function DraftHub() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const bootStartedRef = useRef(false);

  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);

  const createDraftSandboxLeague = async (): Promise<LeagueDetail> => {
    const now = new Date();
    const draftStart = new Date(now.getTime() + 5 * 60 * 1000).toISOString();
    const payload = {
      basics: {
        name: `Draft Sandbox ${now.toLocaleDateString()}`,
        season_year: now.getFullYear(),
        max_teams: 12,
        is_private: false,
        description: "Temporary draft sandbox for branch testing",
        icon_url: null,
      },
      settings: {
        scoring_json: {
          ppr: 1,
          pass_td: 4,
          int: -2,
          rush_td: 6,
          rec_td: 6,
        },
        roster_slots_json: {
          QB: 1,
          RB: 2,
          WR: 2,
          TE: 1,
          K: 1,
          BENCH: 4,
          IR: 1,
        },
        playoff_teams: 4,
        waiver_type: "faab",
        trade_review_type: "commissioner",
        superflex_enabled: false,
        kicker_enabled: true,
        defense_enabled: false,
      },
      draft: {
        draft_datetime_utc: draftStart,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York",
        draft_type: "snake",
        pick_timer_seconds: 90,
        order_strategy: "random",
      },
    };
    const created = await apiPost<LeagueCreateResponse>("/leagues", payload);
    return created.league;
  };

  const isForbiddenOrMissing = (error: unknown) =>
    error instanceof ApiError && (error.status === 403 || error.status === 404);

  const setupDeterministicDraftRoom = async (league: LeagueDetail): Promise<boolean> => {
    try {
      const setupRoom = await apiPost(`/leagues/${league.id}/draft-room/practice-setup`, {
        team_count: 12,
        reset_existing: true,
        start_now: false,
        mock_team_prefix: "Auto Manager",
      });
      queryClient.setQueryData(["league", league.id, "draft-room"], setupRoom);
      const countdownRoom = await apiPost(`/leagues/${league.id}/draft-room/status`, { status: "countdown" });
      queryClient.setQueryData(["league", league.id, "draft-room"], countdownRoom);
      return true;
    } catch (error) {
      if (isForbiddenOrMissing(error)) return false;
      throw error;
    }
  };

  const bootstrapAndEnterDraft = async () => {
    setBootError(null);
    setIsBootstrapping(true);
    try {
      const candidates: LeagueDetail[] = [];

      if (activeLeagueId && Number.isFinite(activeLeagueId)) {
        try {
          const activeLeague = await apiGet<LeagueDetail>(`/leagues/${activeLeagueId}`);
          candidates.push(activeLeague);
        } catch (error) {
          if (!isForbiddenOrMissing(error)) throw error;
          setActiveLeagueId(null);
        }
      }

      try {
        const list = await apiGet<LeagueListResponse>("/leagues", { limit: 20 });
        list.data.forEach((league) => {
          if (!candidates.some((candidate) => candidate.id === league.id)) {
            candidates.push(league);
          }
        });
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) {
          throw error;
        }
      }

      let targetLeague: LeagueDetail | null = null;
      for (const league of candidates) {
        const canEnter = await setupDeterministicDraftRoom(league);
        if (!canEnter) continue;
        targetLeague = league;
        break;
      }

      if (!targetLeague) {
        targetLeague = await createDraftSandboxLeague();
        const canEnterSandbox = await setupDeterministicDraftRoom(targetLeague);
        if (!canEnterSandbox) {
          throw new Error("Unable to initialize draft room for sandbox league.");
        }
      }

      setActiveLeagueId(targetLeague.id);

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["leagues"] }),
        queryClient.invalidateQueries({ queryKey: ["league", targetLeague.id] }),
        queryClient.invalidateQueries({ queryKey: ["league", targetLeague.id, "draft-room"] }),
        queryClient.invalidateQueries({ queryKey: ["league", targetLeague.id, "workspace"] }),
      ]);

      navigate(`/league/${targetLeague.id}/draft`, { replace: true });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to open draft room.";
      setBootError(message || "Unable to open draft room.");
      setIsBootstrapping(false);
    }
  };

  useEffect(() => {
    if (bootStartedRef.current) return;
    bootStartedRef.current = true;
    void bootstrapAndEnterDraft();
    // intentionally one-shot on mount for instant draft entry
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mx-auto max-w-4xl py-16">
      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardContent className="space-y-4 p-10 text-center">
          <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
          <p className="text-[11px] font-black uppercase tracking-[0.25em] text-muted-foreground/80">
            Opening draft room...
          </p>
          {bootError ? (
            <>
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-red-300">{bootError}</p>
              <Button
                className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                onClick={() => void bootstrapAndEnterDraft()}
                disabled={isBootstrapping}
              >
                Retry
              </Button>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
