import argparse
import os
import signal
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import text

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models import load_model_registry
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.services.sportsdata_sync import sync_power4_injuries
from collegefootballfantasy_api.app.services.event_stream import append_league_event
from collegefootballfantasy_api.app.services.notification_service import emit_live_player_alerts
from collegefootballfantasy_api.app.services.scoring_engine import recompute_week_scores
from scripts.ingest_sportsdata_player_stats import ingest_weekly_player_stats

_STOP = False
LIVE_SCORING_LEAGUE_STATUSES = {"draft_live", "post_draft", "active", "in_season"}
LIVE_POLLER_ADVISORY_LOCK_KEY = 77202601


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _on_signal(signum: int, _frame: object) -> None:
    global _STOP
    _STOP = True
    print(f"[{_utc_now()}] Received signal {signum}. Stopping poller...", flush=True)


def _try_acquire_cycle_lock(session) -> bool:
    try:
        row = session.execute(
            text("SELECT pg_try_advisory_lock(:lock_key) AS acquired"),
            {"lock_key": LIVE_POLLER_ADVISORY_LOCK_KEY},
        ).first()
        return bool(row[0]) if row is not None else False
    except Exception:
        session.rollback()
        # Non-Postgres/test environments: allow execution.
        return True


def _release_cycle_lock(session) -> None:
    try:
        session.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": LIVE_POLLER_ADVISORY_LOCK_KEY},
        )
        session.commit()
    except Exception:
        session.rollback()


def _recompute_live_scores_for_leagues(*, session, season: int, week: int) -> dict[str, int]:
    rows = (
        session.query(League.id)
        .filter(League.status.in_(tuple(LIVE_SCORING_LEAGUE_STATUSES)))
        .all()
    )
    league_ids = [int(row[0]) for row in rows]
    completed = 0
    failed = 0
    updated_matchups = 0
    for league_id in league_ids:
        try:
            result = recompute_week_scores(
                session,
                league_id=league_id,
                season=season,
                week=week,
                source_mode="actual_then_projection",
                finalize_matchups=False,
            )
            updated_matchups += len(result.matchup_scores)
            completed += 1
            append_league_event(
                session,
                league_id=league_id,
                event_type="matchup.score.updated",
                entity_type="league",
                entity_id=league_id,
                payload={
                    "season": season,
                    "week": week,
                    "team_scores": len(result.team_scores),
                    "matchup_scores": len(result.matchup_scores),
                    "player_actual_points_used": result.player_actual_points_used,
                    "player_projection_points_used": result.player_projection_points_used,
                },
            )
            append_league_event(
                session,
                league_id=league_id,
                event_type="team.score.updated",
                entity_type="league",
                entity_id=league_id,
                payload={"season": season, "week": week},
            )
            append_league_event(
                session,
                league_id=league_id,
                event_type="player.live.updated",
                entity_type="league",
                entity_id=league_id,
                payload={"season": season, "week": week},
            )
            session.commit()
        except Exception:
            session.rollback()
            failed += 1
    return {
        "eligible_leagues": len(league_ids),
        "completed": completed,
        "failed": failed,
        "updated_matchups": updated_matchups,
    }


def run_loop(
    *,
    season: int,
    week: int,
    interval_seconds: int,
    injuries_interval_seconds: int,
    once: bool,
) -> None:
    global _STOP
    next_injuries_at = 0.0
    cycle = 0

    while not _STOP:
        cycle += 1
        started = time.monotonic()
        started_at = _utc_now()
        stats_result: dict[str, int] | None = None
        injuries_result: dict[str, int | str] | None = None
        scoring_result: dict[str, int] | None = None
        notification_result: dict[str, int] | None = None

        try:
            session = SessionLocal()
            try:
                lock_acquired = _try_acquire_cycle_lock(session)
                if not lock_acquired:
                    print(
                        f"[{started_at}] cycle={cycle} status=skipped reason=lock_not_acquired",
                        flush=True,
                    )
                    if once:
                        break
                    continue
                stats_result = ingest_weekly_player_stats(session, season=season, week=week)
                now_monotonic = time.monotonic()
                if now_monotonic >= next_injuries_at:
                    injuries_result = sync_power4_injuries(
                        session,
                        season=season,
                        week=week,
                        conference=None,
                    )
                    session.commit()
                    next_injuries_at = now_monotonic + injuries_interval_seconds
                scoring_result = _recompute_live_scores_for_leagues(
                    session=session,
                    season=season,
                    week=week,
                )
                notification_result = emit_live_player_alerts(
                    session,
                    season=season,
                    week=week,
                )
                session.commit()
            finally:
                _release_cycle_lock(session)
                session.close()
        except Exception as exc:
            elapsed = time.monotonic() - started
            print(
                f"[{started_at}] cycle={cycle} status=error elapsed={elapsed:.2f}s error={exc}",
                flush=True,
            )
            if once:
                raise
        else:
            elapsed = time.monotonic() - started
            injury_msg = ""
            if injuries_result is not None:
                injury_msg = (
                    " injuries="
                    f"{injuries_result.get('rows_seen', 0)} "
                    f"source={injuries_result.get('source', 'unknown')}"
                )
            scoring_msg = ""
            if scoring_result is not None:
                scoring_msg = (
                    " scoring="
                    f"eligible:{scoring_result.get('eligible_leagues', 0)} "
                    f"completed:{scoring_result.get('completed', 0)} "
                    f"failed:{scoring_result.get('failed', 0)} "
                    f"matchups:{scoring_result.get('updated_matchups', 0)}"
                )
            notification_msg = ""
            if notification_result is not None:
                notification_msg = (
                    " alerts="
                    f"created:{notification_result.get('created', 0)} "
                    f"push:{notification_result.get('push_sent', 0)} "
                    f"injury:{notification_result.get('injury_alerts', 0)} "
                    f"big_play:{notification_result.get('big_play_alerts', 0)}"
                )
            print(
                f"[{started_at}] cycle={cycle} status=ok "
                f"upserted={stats_result.get('upserted', 0) if stats_result else 0} "
                f"skipped={stats_result.get('skipped', 0) if stats_result else 0} "
                f"rows_seen={stats_result.get('rows_seen', 0) if stats_result else 0}"
                f"{injury_msg}{scoring_msg}{notification_msg} elapsed={elapsed:.2f}s",
                flush=True,
            )

        if once:
            break

        sleep_for = max(0.0, interval_seconds - (time.monotonic() - started))
        if sleep_for > 0:
            time.sleep(sleep_for)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Continuously pull SportsData player stats for near-real-time updates."
    )
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--injuries-interval-seconds", type=int, default=120)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    interval_seconds = max(10, args.interval_seconds)
    injuries_interval_seconds = max(interval_seconds, args.injuries_interval_seconds)

    load_model_registry()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    print(
        f"[{_utc_now()}] Starting live stats poller season={args.season} "
        f"week={args.week} interval={interval_seconds}s "
        f"injuries_interval={injuries_interval_seconds}s",
        flush=True,
    )
    run_loop(
        season=args.season,
        week=args.week,
        interval_seconds=interval_seconds,
        injuries_interval_seconds=injuries_interval_seconds,
        once=args.once,
    )
    print(f"[{_utc_now()}] Live stats poller stopped.", flush=True)


if __name__ == "__main__":
    main()
