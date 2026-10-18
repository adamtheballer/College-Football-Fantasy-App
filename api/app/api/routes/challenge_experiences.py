"""Mode routes share the existing authenticated Weekly Challenges namespace."""

from datetime import timedelta
import math
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from collegefootballfantasy_api.app.api.deps import (
    require_verified_user,
    require_admin_user,
)
from collegefootballfantasy_api.app.api.routes.weekly_challenges import mutation_limit
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_challenge import (
    WeeklyChallenge,
    ChallengeRound,
    ChallengeEntry,
)
from collegefootballfantasy_api.app.models.challenge_experience import (
    ChallengeCreator,
    ChallengeExperience,
    ChallengeSurvivorSeries,
    ChallengeCreatorPick,
    ChallengeGameDecision,
    ChallengeManagementAudit,
)
from collegefootballfantasy_api.app.schemas.weekly_challenge import (
    ChallengeRead,
    RoundRead,
    LeaderboardRead,
)
from collegefootballfantasy_api.app.schemas.challenge_experience import (
    CreatorWrite,
    CreatorRead,
    SeriesWrite,
    SeriesRead,
    ExperienceCreate,
    ExperienceConfig,
    AllegianceWrite,
    SchoolRead,
    ModeRead,
    ExperienceLeaderboard,
    DecisionWrite,
    CreatorCorrection,
    VisibilityWrite,
    EventWrite,
    AnalyticsRead,
    RecentResultRead,
    SalarySuggestionRead,
    AnalyticsPreference,
)
from collegefootballfantasy_api.app.services import (
    challenge_experiences as svc,
    weekly_challenges as core,
)

router = APIRouter()
admin_router = APIRouter(dependencies=[Depends(mutation_limit)])


def get_mode(db, cid, *, lock=False):
    c = core.challenge_or_404(db, cid, lock=lock)
    if c.kind not in svc.KINDS:
        svc.fail(
            "INVALID_ENTRY",
            "This is an existing weekly format, not an expanded mode.",
            422,
            c,
        )
    return c


def management_audit(db, user, resource, row, payload):
    db.add(
        ChallengeManagementAudit(
            actor_id=user.id,
            resource=resource,
            resource_id=row.id,
            at=svc.now(),
            details=payload,
        )
    )


@router.get("/modes", response_model=list[ModeRead])
def modes(db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    value = svc.modes(db, user)
    db.commit()
    return value


@router.get("/creators", response_model=list[CreatorRead])
def creators(
    db: Session = Depends(get_db), user: User = Depends(require_verified_user)
):
    return [
        svc.creator_read(c)
        for c in db.query(ChallengeCreator)
        .filter_by(active=True, authorized=True)
        .order_by(ChallengeCreator.name)
    ]


@router.get("/experiences", response_model=list[ChallengeRead])
def competitions(
    kind: str | None = Query(None, pattern="^(fanwars|millionaire|creator|survivor)$"),
    season: int | None = Query(None, ge=2000, le=2100),
    week: int | None = Query(None, ge=1, le=15),
    db: Session = Depends(get_db),
    user: User = Depends(require_verified_user),
):
    season = season or core.settings.current_season_year
    q = (
        db.query(WeeklyChallenge)
        .join(ChallengeRound)
        .join(
            ChallengeExperience, ChallengeExperience.challenge_id == WeeklyChallenge.id
        )
        .filter(
            ChallengeRound.season == season,
            ChallengeExperience.enabled.is_(True),
            WeeklyChallenge.published_at.is_not(None),
        )
    )
    if kind:
        q = q.filter(WeeklyChallenge.kind == kind)
    if week:
        q = q.filter(ChallengeRound.week == week)
    value = [
        svc.read_challenge(db, c, user, include_details=False)
        for c in q.order_by(ChallengeRound.week.desc(), WeeklyChallenge.id).limit(100)
        if svc.visible(db, c)
    ]
    db.commit()
    return value


@router.get("/upcoming", response_model=RoundRead | None)
def upcoming(
    db: Session = Depends(get_db), user: User = Depends(require_verified_user)
):
    year = core.settings.current_season_year
    week = core.competition_week(year, svc.now())
    r = (
        db.query(ChallengeRound)
        .filter(ChallengeRound.season == year, ChallengeRound.week == week + 1)
        .first()
    )
    if not r:
        return None
    value = core.read_round(db, r, user, include_experiences=True)
    db.commit()
    return value


@router.get(
    "/experiences/{challenge_id}/leaderboard", response_model=ExperienceLeaderboard
)
def leaderboard(
    challenge_id: int,
    metric: str = Query("accuracy", pattern="^(accuracy|power)$"),
    conference: str | None = Query(None, pattern="^(SEC|BIG10|BIG12|ACC)$"),
    season: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_verified_user),
):
    c = get_mode(db, challenge_id)
    value = svc.leaderboard(
        db, c, user, metric=metric, conference=conference, season=season
    )
    db.commit()
    return value


@router.put("/experiences/{challenge_id}/allegiance", response_model=SchoolRead)
def allegiance(
    challenge_id: int,
    payload: AllegianceWrite,
    db: Session = Depends(get_db),
    user: User = Depends(mutation_limit),
):
    c = get_mode(db, challenge_id, lock=True)
    m = svc.allegiance(db, c, user, payload.school_id)
    return {"id": m.school_id, "name": m.school_name, "conference": m.conference}


@router.post("/events", response_model=dict[str, bool])
def event(
    payload: EventWrite,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(mutation_limit),
):
    return {
        "recorded": False
        if request.headers.get("dnt") == "1"
        else svc.record_event(
            db, user, payload.event_type, payload.challenge_id, payload.creator_slug
        )
    }


@admin_router.get("/experiences", response_model=list[ChallengeRead])
def admin_competitions(
    season: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=15),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    rows = (
        db.query(WeeklyChallenge)
        .join(ChallengeRound)
        .filter(
            ChallengeRound.season == season,
            ChallengeRound.week == week,
            WeeklyChallenge.kind.in_(svc.KINDS),
        )
        .order_by(WeeklyChallenge.id)
        .all()
    )
    values = [svc.read_challenge(db, c, user, admin=True) for c in rows]
    db.commit()
    return values


@admin_router.post("/experiences", response_model=ChallengeRead, status_code=201)
def create(
    payload: ExperienceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    try:
        c = svc.create(db, payload, user.id)
    except IntegrityError:
        db.rollback()
        svc.fail("DUPLICATE_COMPETITION", "This weekly competition already exists.")
    return svc.read_challenge(db, c, user, admin=True)


@admin_router.put("/experiences/{challenge_id}", response_model=ChallengeRead)
def configure(
    challenge_id: int,
    payload: ExperienceConfig,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    c = get_mode(db, challenge_id, lock=True)
    svc.configure(db, c, payload, user.id)
    return svc.read_challenge(db, c, user, admin=True)


@admin_router.put(
    "/experiences/{challenge_id}/visibility", response_model=ChallengeRead
)
def visibility(
    challenge_id: int,
    payload: VisibilityWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    c = get_mode(db, challenge_id, lock=True)
    if c.version != payload.expected_version:
        svc.fail("VERSION_CONFLICT", "Reload the current configuration.", 409, c)
    svc.detail(db, c).enabled = payload.enabled
    c.version += 1
    core.audit(db, c, user.id, "visibility", payload.model_dump())
    db.commit()
    return svc.read_challenge(db, c, user, admin=True)


@admin_router.get("/creators", response_model=list[CreatorRead])
def admin_creators(
    db: Session = Depends(get_db), user: User = Depends(require_admin_user)
):
    return [
        svc.creator_read(c)
        for c in db.query(ChallengeCreator).order_by(ChallengeCreator.name)
    ]


@admin_router.post("/creators", response_model=CreatorRead, status_code=201)
def create_creator(
    payload: CreatorWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    if db.query(ChallengeCreator.id).filter_by(slug=payload.slug).first():
        svc.fail("DUPLICATE_CREATOR", "Creator slug already exists.")
    if payload.owner_user_id and not db.get(User, payload.owner_user_id):
        svc.fail("INVALID_CONFIGURATION", "Creator account does not exist.", 422)
    row = ChallengeCreator(**payload.model_dump())
    db.add(row)
    db.flush()
    management_audit(db, user, "creator", row, payload.model_dump())
    db.commit()
    return svc.creator_read(row)


@admin_router.put("/creators/{creator_id}", response_model=CreatorRead)
def update_creator(
    creator_id: int,
    payload: CreatorWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    row = (
        db.query(ChallengeCreator)
        .filter_by(id=creator_id)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        svc.fail("NOT_FOUND", "Creator not found.", 404)
    if (
        db.query(ChallengeCreator.id)
        .filter(
            ChallengeCreator.slug == payload.slug, ChallengeCreator.id != creator_id
        )
        .first()
    ):
        svc.fail("DUPLICATE_CREATOR", "Creator slug already exists.")
    if payload.owner_user_id and not db.get(User, payload.owner_user_id):
        svc.fail("INVALID_CONFIGURATION", "Creator account does not exist.", 422)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    management_audit(db, user, "creator", row, payload.model_dump())
    db.commit()
    return svc.creator_read(row)


@admin_router.get("/survivor-series", response_model=list[SeriesRead])
def series(db: Session = Depends(get_db), user: User = Depends(require_admin_user)):
    return [
        svc.series_read(s)
        for s in db.query(ChallengeSurvivorSeries)
        .order_by(ChallengeSurvivorSeries.id.desc())
        .limit(100)
    ]


@admin_router.post("/survivor-series", response_model=SeriesRead, status_code=201)
def create_series(
    payload: SeriesWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    if (
        payload.entry_open_at.tzinfo is None
        or payload.first_lock_at.tzinfo is None
        or payload.end_week < payload.start_week
        or svc.aware(payload.first_lock_at)
        <= max(svc.now(), svc.aware(payload.entry_open_at))
    ):
        svc.fail(
            "INVALID_CONFIGURATION",
            "Set a valid series range, timezone-aware opening and future first lock.",
            422,
        )
    row = ChallengeSurvivorSeries(**payload.model_dump())
    db.add(row)
    db.flush()
    management_audit(db, user, "survivor_series", row, payload.model_dump(mode="json"))
    db.commit()
    return svc.series_read(row)


@admin_router.post(
    "/experiences/{challenge_id}/void-advance", response_model=ChallengeRead
)
def void_advance(
    challenge_id: int,
    payload: DecisionWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    c = get_mode(db, challenge_id, lock=True)
    r = db.get(ChallengeRound, c.round_id)
    if c.kind != "survivor" or c.version != payload.expected_version:
        svc.fail(
            "VERSION_CONFLICT", "Reload a survivor competition before deciding.", 409, c
        )
    g = next((g for g in core.games_for(db, c) if g.id == payload.game_id), None)
    if not g or not (
        core.result_state(g, r, svc.now()) == "void"
        or core.result_state(g, r, svc.now()) == "final"
        and g.home_points == g.away_points
        or (g.schedule_status or "").lower() in {"postponed", "forfeit", "no_contest"}
        and svc.now() >= svc.aware(r.next_rollover_at)
    ):
        svc.fail(
            "INVALID_CONFIGURATION",
            "Only an official tie or void game can be advanced; uncertain games remain pending.",
            422,
            c,
        )
    if (g.schedule_status or "").lower() == "postponed" and svc.now() < svc.aware(
        r.next_rollover_at
    ):
        svc.fail(
            "TEMPORARY_DATA_FAILURE",
            "Wait for the published scoring window to close.",
            409,
            c,
        )
    d = (
        db.query(ChallengeGameDecision)
        .filter_by(challenge_id=c.id, game_id=g.id)
        .one_or_none()
    )
    if d is None:
        db.add(
            ChallengeGameDecision(
                challenge_id=c.id, game_id=g.id, actor_id=user.id, reason=payload.reason
            )
        )
    else:
        d.actor_id = user.id
        d.reason = payload.reason
        d.active = True
    c.version += 1
    core.audit(db, c, user.id, "void_advance", payload.model_dump())
    db.flush()
    svc.settle(db, c, actor=user.id, reason=payload.reason, force=True)
    return svc.read_challenge(db, c, user, admin=True)


@admin_router.put(
    "/experiences/{challenge_id}/creator-correction", response_model=ChallengeRead
)
def creator_correction(
    challenge_id: int,
    payload: CreatorCorrection,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    c = get_mode(db, challenge_id, lock=True)
    if (
        c.kind != "creator"
        or c.version != payload.expected_version
        or not c.published_at
    ):
        svc.fail("VERSION_CONFLICT", "Reload a published creator competition.", 409, c)
    games = {g.id: g for g in core.games_for(db, c)}
    picks = [p.model_dump(exclude_none=True) for p in payload.picks]
    if (
        {p.get("game_id") for p in picks} != set(games)
        or len({p.get("game_id") for p in picks}) != 10
        or any(
            set(p) != {"game_id", "team"}
            or p["team"]
            not in (games[p["game_id"]].home_team, games[p["game_id"]].away_team)
            for p in picks
        )
    ):
        svc.fail(
            "INVALID_ENTRY",
            "Provide one valid creator pick for each of the 10 frozen games.",
            422,
            c,
        )
    before = [
        {"game_id": p.game_id, "team": p.team}
        for p in db.query(ChallengeCreatorPick).filter_by(challenge_id=c.id)
    ]
    db.query(ChallengeCreatorPick).filter_by(challenge_id=c.id).delete(
        synchronize_session=False
    )
    for p in picks:
        db.add(ChallengeCreatorPick(challenge_id=c.id, **p))
    c.version += 1
    core.audit(
        db,
        c,
        user.id,
        "creator_correction",
        {"reason": payload.reason, "before": before, "after": picks},
    )
    db.flush()
    svc.settle(db, c, actor=user.id, reason=payload.reason, force=True)
    return svc.read_challenge(db, c, user, admin=True)


@admin_router.get(
    "/experiences/{challenge_id}/configuration", response_model=ExperienceConfig
)
def configuration(
    challenge_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    from collegefootballfantasy_api.app.models.challenge_experience import (
        ChallengeSalary,
    )

    c = get_mode(db, challenge_id)
    return {
        **{
            k: c.config[k]
            for k in (
                "game_ids",
                "player_ids",
                "correct_points",
                "minimum_fans",
                "rivalries",
            )
            if k in c.config
        },
        "expected_version": c.version,
        "salaries": [
            {"player_id": s.player_id, "salary": float(s.salary)}
            for s in db.query(ChallengeSalary).filter_by(challenge_id=c.id)
        ],
        "creator_picks": [
            {"game_id": s.game_id, "team": s.team}
            for s in db.query(ChallengeCreatorPick).filter_by(challenge_id=c.id)
        ],
    }


@admin_router.get(
    "/experiences/{challenge_id}/salary-suggestions",
    response_model=list[SalarySuggestionRead],
)
def suggestions(
    challenge_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    c = get_mode(db, challenge_id)
    r = db.get(ChallengeRound, c.round_id)
    if c.kind != "millionaire":
        svc.fail(
            "INVALID_CONFIGURATION",
            "Salary suggestions belong to Fantasy Millionaire.",
            422,
            c,
        )
    # Review-only salary v1. Reuse the exact trusted projection gate used at publication.
    eligible = {p["id"] for p in core.catalog(db, r.season, r.week)["players"]}
    return [
        {
            "player_id": pid,
            "salary": min(30, max(1, math.floor(points * 0.8 + 0.5))),
            "projection": points,
            "rule": "review-required-salary-v1",
        }
        for pid, points in svc.published_projections(db, c, eligible).items()
    ]


@admin_router.get("/experiences/{challenge_id}/analytics", response_model=AnalyticsRead)
def analytics(
    challenge_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    return svc.analytics(db, get_mode(db, challenge_id))


@router.get("/my-results", response_model=list[RecentResultRead])
def my_results(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_verified_user),
):
    from collegefootballfantasy_api.app.models.weekly_challenge import ChallengeScore

    rows = (
        db.query(WeeklyChallenge, ChallengeRound, ChallengeScore)
        .join(ChallengeRound)
        .join(ChallengeEntry, ChallengeEntry.challenge_id == WeeklyChallenge.id)
        .join(ChallengeScore, ChallengeScore.entry_id == ChallengeEntry.id)
        .filter(
            ChallengeEntry.user_id == user.id,
            ChallengeScore.status.in_(["final", "no_contest"]),
        )
        .order_by(
            ChallengeRound.season.desc(), ChallengeRound.week.desc(), WeeklyChallenge.id
        )
        .limit(limit)
    )
    return [
        {
            "challenge_id": c.id,
            "kind": c.kind,
            "name": svc.KINDS.get(c.kind, core.KINDS.get(c.kind, c.kind)),
            "season": r.season,
            "week": r.week,
            "raw_points": float(s.raw_points) if s.raw_points is not None else None,
            "rank": s.rank,
            "status": s.status,
        }
        for c, r, s in rows
    ]


@admin_router.post(
    "/experiences/{challenge_id}/revoke-void-advance", response_model=ChallengeRead
)
def revoke_void(
    challenge_id: int,
    payload: DecisionWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    c = get_mode(db, challenge_id, lock=True)
    if c.kind != "survivor" or c.version != payload.expected_version:
        svc.fail("VERSION_CONFLICT", "Reload the survivor competition.", 409, c)
    decision = (
        db.query(ChallengeGameDecision)
        .filter_by(challenge_id=c.id, game_id=payload.game_id, active=True)
        .one_or_none()
    )
    if decision is None:
        svc.fail("NOT_FOUND", "Active void decision not found.", 404, c)
    decision.active = False
    c.version += 1
    core.audit(db, c, user.id, "revoke_void_advance", payload.model_dump())
    db.flush()
    svc.settle(db, c, actor=user.id, reason=payload.reason, force=True)
    return svc.read_challenge(db, c, user, admin=True)


@router.get("/analytics-preference", response_model=AnalyticsPreference)
def analytics_preference(
    db: Session = Depends(get_db), user: User = Depends(require_verified_user)
):
    from collegefootballfantasy_api.app.models.challenge_experience import (
        ChallengeAnalyticsPreference,
    )

    row = db.get(ChallengeAnalyticsPreference, user.id)
    return {"enabled": row.enabled if row else True}


@router.put("/analytics-preference", response_model=AnalyticsPreference)
def save_analytics_preference(
    payload: AnalyticsPreference,
    db: Session = Depends(get_db),
    user: User = Depends(mutation_limit),
):
    from collegefootballfantasy_api.app.models.challenge_experience import (
        ChallengeAnalyticsPreference,
    )

    db.query(User).filter_by(id=user.id).with_for_update().one()
    row = db.get(ChallengeAnalyticsPreference, user.id)
    if row is None:
        row = ChallengeAnalyticsPreference(user_id=user.id)
        db.add(row)
    row.enabled = payload.enabled
    db.commit()
    return {"enabled": row.enabled}
