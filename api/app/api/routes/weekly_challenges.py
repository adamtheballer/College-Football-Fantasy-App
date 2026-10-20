from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_verified_user, require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_challenge import ChallengeRound, WeeklyChallenge, ChallengeRecognition, ChallengeAudit
from collegefootballfantasy_api.app.schemas.weekly_challenge import (
    RoundRead, ChallengeRead, EntryRead, EntryWrite, ChallengeConfig,
    DuelInvite, DuelRead, ResultsRead, LeaderboardRead, Participant, ProfileRead,
    CatalogRead, AdminAction, ValidationRead, AuditRead,
)
from collegefootballfantasy_api.app.services import weekly_challenges as service
from collegefootballfantasy_api.app.services.auth_security import enforce_auth_rate_limit

router = APIRouter()


def mutation_limit(request: Request, db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    expected = request.headers.get("x-cffb-challenge-account")
    if expected is not None and expected != str(user.id):
        service.fail("VERSION_CONFLICT", "Your signed-in account changed. Reload before saving.")
    enforce_auth_rate_limit(db, action="weekly_challenge_mutation", identifier=str(user.id), request=request, limit=60, window_seconds=60, include_ip=False)
    # Count unsuccessful requests too. No domain mutation has happened yet.
    db.commit()
    return user


admin_router = APIRouter(dependencies=[Depends(mutation_limit)])


@router.get("/current", response_model=RoundRead)
def current(include_experiences: bool = False, db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    r = service.ensure_round(db, service.settings.current_season_year, service.competition_week(service.settings.current_season_year, service.utcnow()))
    result = service.read_round(db, r, user, include_experiences=include_experiences)
    db.commit()
    return result


@router.get("/history", response_model=list[RoundRead])
def history(include_experiences: bool = False, limit: int = Query(15, ge=1, le=30), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    year = service.settings.current_season_year
    week = service.competition_week(year, service.utcnow())
    published = select(WeeklyChallenge.round_id).where(WeeklyChallenge.published_at.is_not(None))
    rows = db.query(ChallengeRound).filter(
        or_(ChallengeRound.season < year, and_(ChallengeRound.season == year, ChallengeRound.week <= week)),
        or_(ChallengeRound.id.in_(published), and_(ChallengeRound.season == year, ChallengeRound.week == week)),
    ).order_by(ChallengeRound.season.desc(), ChallengeRound.week.desc()).limit(limit).offset(offset).all()
    result = [service.read_round(db, r, user, include_experiences=include_experiences) for r in rows]
    db.commit()
    return result


@router.get("/rounds/{round_id}", response_model=RoundRead)
def round_detail(round_id: int, include_experiences: bool = False, db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    r = db.get(ChallengeRound, round_id)
    if r is None: service.fail("NOT_FOUND", "Round not found.", 404)
    result = service.read_round(db, r, user, include_experiences=include_experiences)
    db.commit()
    return result


@router.get("/leaderboard", response_model=LeaderboardRead)
def leaderboard(season: int = Query(..., ge=2000, le=2100), round_id: int | None = Query(None, gt=0), league_id: int | None = Query(None, gt=0), db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    if round_id is not None:
        r = db.get(ChallengeRound, round_id)
        if r is None or r.season != season: service.fail("NOT_FOUND", "Round does not belong to this season.", 404)
    return service.leaderboard(db, user, season=season, round_id=round_id, league_id=league_id)


@router.get("/participants", response_model=list[Participant])
def participants(q: str = Query(..., min_length=2, max_length=80), db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    # Existing public manager fields, never email/contact/account security data.
    text = q.replace("%", "\\%").replace("_", "\\_")
    rows = db.query(User).filter(User.is_active.is_(True), User.id != user.id,
        or_(func.lower(User.first_name).like(f"%{text.lower()}%", escape="\\"), func.lower(User.username).like(f"%{text.lower()}%", escape="\\"))).order_by(User.first_name, User.id).limit(20)
    return [service.participant(u) for u in rows]


@router.get("/participants/{user_id}", response_model=ProfileRead)
def profile(user_id: int, db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    target = db.get(User, user_id)
    if target is None or not target.is_active: service.fail("NOT_FOUND", "Manager not found.", 404)
    badges = db.query(ChallengeRecognition).filter_by(user_id=user_id, active=True).order_by(ChallengeRecognition.round_id.desc()).limit(50).all()
    rounds = {r.id:r for r in db.query(ChallengeRound).filter(ChallengeRound.id.in_({b.round_id for b in badges}))}
    def label(code):
        return "Weekly Winner" if code == "weekly_winner" else f"{service.KINDS.get(code.removesuffix('_winner'), 'Challenge')} Winner"
    return {**service.participant(target), "recognition": [f"{label(b.code)} · {rounds[b.round_id].season} Week {rounds[b.round_id].week}" for b in badges]}


@router.get("/challenges/{challenge_id}", response_model=ChallengeRead)
def detail(challenge_id: int, db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    result = service.read_challenge(db, service.challenge_or_404(db, challenge_id, lock=True), user)
    db.commit()
    return result


@router.get("/challenges/{challenge_id}/entry", response_model=EntryRead | None)
def own_entry(challenge_id: int, db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    return service.entry_for(db, service.challenge_or_404(db, challenge_id), user.id)


@router.put("/challenges/{challenge_id}/entry", response_model=EntryRead)
def save_entry(challenge_id: int, payload: EntryWrite, db: Session = Depends(get_db), user: User = Depends(mutation_limit)):
    return service.save_entry(db, service.challenge_or_404(db, challenge_id, lock=True), user, payload)


@router.get("/challenges/{challenge_id}/results", response_model=ResultsRead)
def results(challenge_id: int, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    return service.results(db, service.challenge_or_404(db, challenge_id), user, limit, offset)


@router.get("/challenges/{challenge_id}/duels", response_model=list[DuelRead])
def duels(challenge_id: int, db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    return service.read_duels(db, service.challenge_or_404(db, challenge_id), user)


@router.post("/challenges/{challenge_id}/duels", response_model=list[DuelRead], status_code=201)
def invite(challenge_id: int, payload: DuelInvite, db: Session = Depends(get_db), user: User = Depends(mutation_limit)):
    c = service.challenge_or_404(db, challenge_id, lock=True)
    service.invite_duel(db, c, user, payload.invitee_id)
    return service.read_duels(db, c, user)


@router.post("/challenges/{challenge_id}/duels/{duel_id}/{action}", response_model=list[DuelRead])
def respond(challenge_id: int, duel_id: int, action: str, db: Session = Depends(get_db), user: User = Depends(mutation_limit)):
    if action not in {"accept", "decline"}: service.fail("INVALID_DUEL", "Use accept or decline.", 422)
    c = service.challenge_or_404(db, challenge_id, lock=True)
    service.respond_duel(db, c, user, duel_id, action == "accept")
    return service.read_duels(db, c, user)


@admin_router.post("/rounds/{season}/{week}", response_model=RoundRead)
def prepare(season: int, week: int, db: Session = Depends(get_db), user: User = Depends(require_admin_user)):
    if not 2000 <= season <= 2100 or not 1 <= week <= 15: service.fail("INVALID_CONFIGURATION", "Use a valid season and canonical week 1–15.", 422)
    r = service.ensure_round(db, season, week)
    result = service.read_round(db, r, user, admin=True)
    db.commit()
    return result


@admin_router.get("/catalog", response_model=CatalogRead)
def catalog(season: int = Query(..., ge=2000, le=2100), week: int = Query(..., ge=1, le=15), db: Session = Depends(get_db), user: User = Depends(require_admin_user)):
    return service.catalog(db, season, week)


@admin_router.get("/challenges/{challenge_id}", response_model=ChallengeRead)
def admin_detail(challenge_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin_user)):
    c = service.challenge_or_404(db, challenge_id, lock=True)
    result = service.read_challenge(db, c, user, admin=True)
    db.commit()
    return result


@admin_router.put("/challenges/{challenge_id}", response_model=ChallengeRead)
def configure(challenge_id: int, payload: ChallengeConfig, db: Session = Depends(get_db), user: User = Depends(require_admin_user)):
    c = service.challenge_or_404(db, challenge_id, lock=True)
    service.configure(db, c, payload, user.id)
    return service.read_challenge(db, c, user, admin=True)


@admin_router.post("/challenges/{challenge_id}/validate", response_model=ValidationRead)
def validate(challenge_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin_user)):
    c = service.challenge_or_404(db, challenge_id)
    issues, games = service.validate_config(db, c, c.config)
    return {"valid": not issues, "blockers": issues, "lock_at": min(service.aware(g.start_date) for g in games if g.start_date)-service.timedelta(minutes=5) if any(g.start_date for g in games) else None}


@admin_router.post("/challenges/{challenge_id}/{action}", response_model=ChallengeRead)
def admin_action(challenge_id: int, action: str, payload: AdminAction, db: Session = Depends(get_db), user: User = Depends(require_admin_user)):
    c = service.challenge_or_404(db, challenge_id, lock=True)
    if c.version != payload.expected_version: service.fail("VERSION_CONFLICT", "Configuration changed. Reload first.", challenge=c)
    if action == "publish": service.publish(db, c, payload.expected_version, user.id)
    elif action == "cancel": service.cancel(db, c, user.id, payload.expected_version, payload.reason)
    elif action in {"score", "correct"}: service.settle(db, c, actor=user.id, reason=payload.reason, force=True)
    else: service.fail("INVALID_CONFIGURATION", "Unknown administration action.", 422, c)
    return service.read_challenge(db, c, user, admin=True)


@admin_router.get("/challenges/{challenge_id}/audit", response_model=list[AuditRead])
def audit(challenge_id: int, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(require_admin_user)):
    service.challenge_or_404(db, challenge_id)
    return db.query(ChallengeAudit).filter_by(challenge_id=challenge_id).order_by(ChallengeAudit.id.desc()).limit(limit).offset(offset).all()
