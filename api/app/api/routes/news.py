from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.app.api.deps import get_current_user
from api.app.db.session import get_db
from api.app.integrations.college_football_news import CollegeFootballNewsProvider
from api.app.models.news_item import NewsItem
from api.app.models.user import User
from api.app.schemas.news import ManualNewsCreate, NewsIngestRunResponse, NewsItemRead, NewsListResponse, is_breaking_news
from api.app.services.news_ingestion import create_manual_news_item, run_news_ingestion


router = APIRouter()


def _news_item_read(row: NewsItem) -> NewsItemRead:
    return NewsItemRead(
        id=row.id,
        title=row.title,
        summary=row.summary,
        category=row.category,
        source_name=row.source_name,
        source_url=row.source_url,
        published_at=row.published_at,
        player_id=row.player_id,
        player_name_raw=row.player_name_raw,
        team_name_raw=row.team_name_raw,
        canonical_team=row.canonical_team,
        position=row.position,
        confidence_score=float(row.confidence_score or 0),
        fantasy_relevance_score=float(row.fantasy_relevance_score or 0),
        fantasy_impact=row.fantasy_impact,
        tags=list(row.tags_json or []),
        is_breaking=is_breaking_news(row.published_at),
    )


def _feed_query(
    db: Session,
    *,
    category: str | None,
    team: str | None,
    player_id: int | None,
    position: str | None,
    min_relevance: float,
    breaking_only: bool,
):
    query = db.query(NewsItem).filter(NewsItem.status.in_(["new", "reviewed"]))
    if category:
        query = query.filter(NewsItem.category == category)
    if team:
        query = query.filter(func.lower(NewsItem.canonical_team) == team.lower())
    if player_id:
        query = query.filter(NewsItem.player_id == player_id)
    if position:
        query = query.filter(func.upper(NewsItem.position) == position.upper())
    if min_relevance:
        query = query.filter(NewsItem.fantasy_relevance_score >= min_relevance)
    if breaking_only:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
        query = query.filter(NewsItem.published_at.is_not(None), NewsItem.published_at >= cutoff)
    return query


def _list_news(
    db: Session,
    *,
    category: str | None = None,
    team: str | None = None,
    player_id: int | None = None,
    position: str | None = None,
    limit: int = 12,
    offset: int = 0,
    min_relevance: float = 0,
    breaking_only: bool = False,
) -> NewsListResponse:
    query = _feed_query(
        db,
        category=category,
        team=team,
        player_id=player_id,
        position=position,
        min_relevance=min_relevance,
        breaking_only=breaking_only,
    )
    total = query.count()
    rows = (
        query.order_by(NewsItem.fantasy_relevance_score.desc(), NewsItem.published_at.desc().nullslast(), NewsItem.discovered_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return NewsListResponse(data=[_news_item_read(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/feed", response_model=NewsListResponse)
def get_news_feed(
    category: str | None = Query(default=None),
    team: str | None = Query(default=None),
    player_id: int | None = Query(default=None),
    position: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    min_relevance: float = Query(default=0, ge=0, le=100),
    breaking_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> NewsListResponse:
    return _list_news(
        db,
        category=category,
        team=team,
        player_id=player_id,
        position=position,
        limit=limit,
        offset=offset,
        min_relevance=min_relevance,
        breaking_only=breaking_only,
    )


@router.get("/breaking", response_model=NewsListResponse)
def get_breaking_news(
    limit: int = Query(default=12, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> NewsListResponse:
    return _list_news(db, limit=limit, offset=offset, min_relevance=35, breaking_only=True)


@router.get("/transfers", response_model=NewsListResponse)
def get_transfer_news(
    limit: int = Query(default=12, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> NewsListResponse:
    return _list_news(db, category="transfer", limit=limit, offset=offset)


@router.get("/source-preview")
def source_preview(
    limit: int = Query(default=10, ge=1, le=25),
    _current_user: User = Depends(get_current_user),
) -> dict:
    entries = CollegeFootballNewsProvider().fetch_entries(limit=limit)
    return {
        "source": "College Football News",
        "data": [
            {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary,
                "published_at": entry.published_at.isoformat() if entry.published_at else None,
                "external_id": entry.external_id,
            }
            for entry in entries
        ],
    }


@router.post("/manual", response_model=NewsItemRead)
def create_manual_news(
    payload: ManualNewsCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> NewsItemRead:
    return _news_item_read(create_manual_news_item(db, payload=payload))


@router.post("/ingest", response_model=NewsIngestRunResponse)
def ingest_news(
    source: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=100),
    force: bool = Query(default=False),
    dry_run: bool = Query(default=False),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> NewsIngestRunResponse:
    return run_news_ingestion(db, source_slug=source, limit=limit, force=force, dry_run=dry_run)


@router.patch("/{news_id}/hide", response_model=NewsItemRead)
def hide_news_item(
    news_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> NewsItemRead:
    item = db.get(NewsItem, news_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News item not found.")
    item.status = "hidden"
    db.add(item)
    db.commit()
    db.refresh(item)
    return _news_item_read(item)


@router.patch("/{news_id}/review", response_model=NewsItemRead)
def review_news_item(
    news_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> NewsItemRead:
    item = db.get(NewsItem, news_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News item not found.")
    item.status = "reviewed"
    db.add(item)
    db.commit()
    db.refresh(item)
    return _news_item_read(item)
