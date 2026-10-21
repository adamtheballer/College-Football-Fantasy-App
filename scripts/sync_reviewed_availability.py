"""Apply versioned, corroborated reports once, then audit effective absences.

This supplements pending conference reports. It never treats an omitted athlete
as healthy, imports an old game as current, or rewrites completed-week points.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from scripts.apply_injury_projection_correction import apply_correction
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.models.player_news_event import PlayerNewsEvent
from collegefootballfantasy_api.app.services.availability_corrections import MANUAL_CORROBORATED_SOURCE, publish_zero_projection_for_unavailable_player
from collegefootballfantasy_api.app.services.injury_status import reviewed_injuries_for_week
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter
from collegefootballfantasy_api.app.services.power4 import conference_for_school
from collegefootballfantasy_api.app.services.provider_cache import get_or_create_sync_state, mark_sync_attempt, scope_dict_to_key

MANIFEST = Path(__file__).resolve().parents[1] / "reports/availability/2026-reviewed-corrections.json"


def sync_reviewed_reports(*, season: int, week: int) -> dict:
    ensure_models_registered()
    seeded = 0
    correction_errors = []
    for record in json.loads(MANIFEST.read_text()):
        if record["season"] != season or not record["week"] <= week <= record["effective_until_week"]:
            continue
        try:
            with SessionLocal() as db:
                player = db.scalars(select(Player).where(Player.name == record["player"], Player.school == record["school"], Player.position == record["position"])).one_or_none()
                if player is None:
                    raise ValueError(f"No exact catalog identity for {record['player']}")
                saved = db.scalar(select(PlayerAvailabilityEvent.id).where(
                    PlayerAvailabilityEvent.player_id == player.id,
                    PlayerAvailabilityEvent.season == season,
                    PlayerAvailabilityEvent.source == MANUAL_CORROBORATED_SOURCE,
                    PlayerAvailabilityEvent.source_url == record["source_url"][0],
                    PlayerAvailabilityEvent.reviewed.is_(True),
                ))
                newer_return = db.scalar(select(PlayerAvailabilityEvent.id).where(
                    PlayerAvailabilityEvent.player_id == player.id,
                    PlayerAvailabilityEvent.season == season,
                    PlayerAvailabilityEvent.reviewed.is_(True),
                    PlayerAvailabilityEvent.status.in_(("FULL", "AVAILABLE", "ACTIVE")),
                    PlayerAvailabilityEvent.week >= record["week"],
                    PlayerAvailabilityEvent.week <= week,
                    PlayerAvailabilityEvent.published_at > datetime.fromisoformat(record["published_at"]),
                ))
                if saved is not None or newer_return is not None:
                    continue  # Never replay an old report over a newer return update.
            args = argparse.Namespace(**{key:value for key,value in record.items() if key not in {"position", "published_at"}}, require_corroboration=True, apply=True)
            args.week = week  # Never change an already-completed week during a late deployment.
            apply_correction(args)
            with SessionLocal() as db:
                event = db.scalar(select(PlayerAvailabilityEvent).where(PlayerAvailabilityEvent.player_id == player.id, PlayerAvailabilityEvent.season == season, PlayerAvailabilityEvent.week == week, PlayerAvailabilityEvent.source == MANUAL_CORROBORATED_SOURCE))
                event.published_at = datetime.fromisoformat(record["published_at"])
                news = db.scalar(select(PlayerNewsEvent).where(PlayerNewsEvent.player_id == player.id, PlayerNewsEvent.season == season, PlayerNewsEvent.week == week, PlayerNewsEvent.source == MANUAL_CORROBORATED_SOURCE))
                if news is not None:
                    news.published_at = event.published_at
                db.commit()
            seeded += 1
        except Exception as exc:
            correction_errors.append({"player":record["player"],"error":type(exc).__name__})

    with SessionLocal() as db:
        players = db.scalars(select(Player).where(canonical_fantasy_player_filter(season))).all()
        reports = reviewed_injuries_for_week(db, season=season, week=week, player_ids={p.id for p in players})
        projections_corrected = 0
        for player in players:
            report = reports.get(player.id)
            if report is None:
                continue
            correction = publish_zero_projection_for_unavailable_player(
                db, player=player, season=season, week=week,
                status=report.status, note=report.notes or "Reviewed effective absence",
            )
            projections_corrected += correction is not None
        db.flush()
        reports = reviewed_injuries_for_week(db, season=season, week=week, player_ids={p.id for p in players})
        counts = {}
        for p in players:
            conf = conference_for_school(p.school) or "INDEPENDENT"
            counts.setdefault(conf, {"players":0,"current_designations":0,"unreported":0})
            counts[conf]["players"] += 1
            counts[conf]["current_designations" if p.id in reports else "unreported"] += 1
        result = {"seeded":seeded,"projections_corrected":projections_corrected,"players_audited":len(players),"correction_errors":correction_errors,"conferences":counts}
        state = get_or_create_sync_state(db,"reviewed_availability_audit","player_pool",scope_dict_to_key({"season":season,"week":week}))
        mark_sync_attempt(db,state=state,status="ready")
        state.meta = result
        db.commit()
        return result
