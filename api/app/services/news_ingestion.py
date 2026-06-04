from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.app.integrations.college_football_news import CFN_HOME_URL, CFN_SOURCE_NAME, CollegeFootballNewsProvider
from api.app.models.news_item import NewsItem
from api.app.models.news_source import NewsSource
from api.app.schemas.news import ManualNewsCreate, NewsIngestRunResponse
from api.app.services.news_classifier import category_fantasy_impact, classify_news
from api.app.services.news_matching import match_news_entities
from api.app.services.news_relevance import compute_fantasy_relevance


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_content_hash(*, source_url: str, title: str) -> str:
    return hashlib.sha256(f"{source_url.strip().lower()}|{title.strip().lower()}".encode("utf-8")).hexdigest()


def ensure_default_news_source(db: Session) -> NewsSource:
    source = db.query(NewsSource).filter(NewsSource.name == CFN_SOURCE_NAME).first()
    if source:
        return source
    source = NewsSource(
        name=CFN_SOURCE_NAME,
        source_type="html_index",
        url=CFN_HOME_URL,
        active=True,
        priority=80,
        poll_interval_minutes=60,
    )
    db.add(source)
    db.flush()
    return source


def _source_due(source: NewsSource, *, force: bool, now: datetime) -> bool:
    if force or source.last_polled_at is None:
        return True
    last_polled_at = source.last_polled_at
    if last_polled_at.tzinfo is None:
        last_polled_at = last_polled_at.replace(tzinfo=timezone.utc)
    return last_polled_at + timedelta(minutes=int(source.poll_interval_minutes or 60)) <= now


def _upsert_news_item(
    db: Session,
    *,
    source: NewsSource,
    entry: Any,
    now: datetime,
    min_relevance: float,
) -> tuple[str, NewsItem | None]:
    title = (entry.title or "").strip()
    source_url = (entry.link or "").strip()
    if not title or not source_url:
        return "low_relevance", None
    category = classify_news(title, entry.summary)
    match = match_news_entities(db, title=title, summary=entry.summary)
    relevance = compute_fantasy_relevance(
        category=category,
        title=title,
        summary=entry.summary,
        published_at=entry.published_at,
        player_id=match.player_id,
        canonical_team=match.canonical_team,
        position=match.position,
        now=now,
    )
    if relevance < min_relevance:
        return "low_relevance", None
    content_hash = compute_content_hash(source_url=source_url, title=title)
    existing = (
        db.query(NewsItem)
        .filter((NewsItem.content_hash == content_hash) | (func.lower(NewsItem.source_url) == source_url.lower()))
        .first()
    )
    payload = {
        **(entry.raw_payload or {}),
        "external_id": entry.external_id,
        "published_at": entry.published_at.isoformat() if entry.published_at else None,
    }
    if existing:
        existing.summary = entry.summary or existing.summary
        existing.published_at = entry.published_at or existing.published_at
        existing.category = category
        existing.player_id = match.player_id
        existing.player_name_raw = match.player_name_raw
        existing.team_name_raw = match.team_name_raw
        existing.canonical_team = match.canonical_team
        existing.position = match.position
        existing.confidence_score = match.confidence_score
        existing.fantasy_relevance_score = relevance
        existing.fantasy_impact = category_fantasy_impact(category)
        existing.tags_json = sorted({category, *(filter(None, [match.canonical_team, match.position]))})
        existing.raw_payload_json = payload
        db.add(existing)
        return "updated", existing
    item = NewsItem(
        external_id=entry.external_id,
        source_name=source.name,
        source_url=source_url,
        source_type=source.source_type,
        title=title,
        summary=entry.summary,
        content_hash=content_hash,
        category=category,
        status="new",
        published_at=entry.published_at,
        discovered_at=now,
        player_id=match.player_id,
        player_name_raw=match.player_name_raw,
        team_name_raw=match.team_name_raw,
        canonical_team=match.canonical_team,
        position=match.position,
        confidence_score=match.confidence_score,
        fantasy_relevance_score=relevance,
        fantasy_impact=category_fantasy_impact(category),
        tags_json=sorted({category, *(filter(None, [match.canonical_team, match.position]))}),
        raw_payload_json=payload,
    )
    db.add(item)
    db.flush()
    return "inserted", item


def run_news_ingestion(
    db: Session,
    *,
    source_slug: str = "all",
    limit: int = 50,
    force: bool = False,
    dry_run: bool = False,
    min_relevance: float = 20,
) -> NewsIngestRunResponse:
    ensure_default_news_source(db)
    query = db.query(NewsSource).filter(NewsSource.active.is_(True)).order_by(NewsSource.priority.desc(), NewsSource.id.asc())
    if source_slug == "cfn":
        query = query.filter(NewsSource.name == CFN_SOURCE_NAME)
    sources = query.all()
    now = now_utc()
    summary = {
        "sources_checked": 0,
        "rows_seen": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "duplicates_skipped": 0,
        "low_relevance_skipped": 0,
        "errors": [],
    }
    provider = CollegeFootballNewsProvider()
    for source in sources:
        if not _source_due(source, force=force, now=now):
            continue
        summary["sources_checked"] += 1
        source.last_polled_at = now
        try:
            entries = provider.fetch_entries(limit=limit) if source.name == CFN_SOURCE_NAME else []
            summary["rows_seen"] += len(entries)
            for entry in entries:
                result, item = _upsert_news_item(db, source=source, entry=entry, now=now, min_relevance=min_relevance)
                if result == "inserted":
                    summary["rows_inserted"] += 1
                elif result == "updated":
                    summary["rows_updated"] += 1
                elif result == "low_relevance":
                    summary["low_relevance_skipped"] += 1
                else:
                    summary["duplicates_skipped"] += 1
                if dry_run and item:
                    db.expunge(item)
            source.last_success_at = now
            source.last_error = None
        except Exception as exc:
            source.last_error = str(exc)[:1000]
            summary["errors"].append({"source": source.name, "error": source.last_error})
        db.add(source)
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return NewsIngestRunResponse(**summary)


def create_manual_news_item(db: Session, *, payload: ManualNewsCreate) -> NewsItem:
    now = now_utc()
    category = payload.category or classify_news(payload.title, payload.summary)
    match = match_news_entities(db, title=payload.title, summary=payload.summary)
    player_id = payload.player_id if payload.player_id is not None else match.player_id
    position = match.position
    relevance = compute_fantasy_relevance(
        category=category,
        title=payload.title,
        summary=payload.summary,
        published_at=payload.published_at,
        player_id=player_id,
        canonical_team=payload.team_name_raw or match.canonical_team,
        position=position,
        now=now,
    )
    content_hash = compute_content_hash(source_url=payload.source_url, title=payload.title)
    existing = db.query(NewsItem).filter((NewsItem.content_hash == content_hash) | (func.lower(NewsItem.source_url) == payload.source_url.lower())).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="News item already exists.")
    item = NewsItem(
        external_id=None,
        source_name=payload.source_name,
        source_url=payload.source_url,
        source_type="manual",
        title=payload.title,
        summary=payload.summary,
        content_hash=content_hash,
        category=category,
        status="new",
        published_at=payload.published_at,
        discovered_at=now,
        player_id=player_id,
        player_name_raw=payload.player_name_raw or match.player_name_raw,
        team_name_raw=payload.team_name_raw or match.team_name_raw,
        canonical_team=payload.team_name_raw or match.canonical_team,
        position=position,
        confidence_score=match.confidence_score,
        fantasy_relevance_score=relevance,
        fantasy_impact=payload.fantasy_impact or category_fantasy_impact(category),
        tags_json=payload.tags or [category],
        raw_payload_json={"source": "manual"},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
