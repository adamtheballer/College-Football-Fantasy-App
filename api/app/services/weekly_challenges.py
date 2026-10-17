"""Weekly competitions: a single app-wide round, serialized mutations and audited awards.

Never calls providers, changes a league roster or trusts client scoring. Transaction
ownership is here for mutations; callers roll back on exceptions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.scoring_engine import CALCULATION_VERSION
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_challenge import (
    ChallengeRound, WeeklyChallenge, ChallengeSlateGame, ChallengePoolPlayer,
    ChallengeEntry, ChallengeDuel, ChallengeDuelSeat, ChallengeScore,
    ChallengeAward, ChallengeRecognition, ChallengeAudit,
)
from collegefootballfantasy_api.app.schemas.weekly_challenge import ChallengeConfig, EntryWrite
from collegefootballfantasy_api.app.scoring import get_scoring_rules
from collegefootballfantasy_api.app.services.league_weeks import calendar_matchup_display_week, matchup_display_rollover_at
from collegefootballfantasy_api.app.services.player_chart_publication import points_from_verified_stats
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter, season_eligible_player_filter
from collegefootballfantasy_api.app.services.fantasy_game_selection import school_key, fantasy_games_by_school
from collegefootballfantasy_api.app.services.injury_status import confirmed_nonparticipant_ids
from collegefootballfantasy_api.app.services.weekly_challenge_sponsors import weekly_challenge_sponsor

KINDS = {"slate12": "Slate 12", "upset": "Upset Hunter", "fantasy5": "Fantasy Five", "lock": "Lock of the Week", "duels": "Rivalry Duels"}
RULES = {
    "slate12": "Pick all 12 straight-up winners: 1 point per correct pick. Predict the featured game's combined score; smallest absolute error breaks placement ties, without extra season points. Exact ties share rank.",
    "upset": "Select 3 published underdogs from different games. Each correct upset earns its frozen 1–5 difficulty points; maximum 15. Other picks earn 0.",
    "fantasy5": "Choose 5 distinct Power 4/approved-pool players: QB, RB, WR, TE and RB/WR/TE FLEX. Frozen standard CFFB scoring determines raw totals. Competition ranks 1–10 receive 10–1 challenge points; tied ranks receive equal awards.",
    "lock": "Select one team from the eligible slate. A straight-up win earns 5 challenge points; otherwise 0.",
    "duels": "Both managers must submit 5 winner predictions and accept before the shared deadline. One accepted duel per account. More correct picks wins 5 points; a draw earns 2 each; a loss earns 0. Unmatched invitations earn no win.",
}
DISRUPTION_RULE = " All entries lock 5 minutes before the earliest published kickoff. Canceled games, and games postponed beyond the next Matchup weekly rollover, are void (0). Delays remain pending. All games void means no contest and no awards. Free entry; recognition and cosmetic badges have no redeemable value."
FINAL = {"final", "post", "completed"}
VOID = {"canceled", "cancelled", "void"}
SCHEDULED = {"scheduled", "pre", "pregame", "not_started"}
UNSTARTED = SCHEDULED | VOID | {"delayed", "postponed"}


def utcnow():
    return datetime.now(timezone.utc)


def competition_week(season, now=None):
    week = calendar_matchup_display_week(season, now)
    return max(week, settings.weekly_challenges_launch_week) if season == settings.weekly_challenges_launch_season else week


def aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def fail(code, message, status=409, challenge=None):
    raise HTTPException(status, detail={"code": code, "message": message,
        "challenge_id": challenge.id if challenge else None,
        "round_id": challenge.round_id if challenge else None,
        "lock_at": aware(challenge.lock_at).isoformat() if challenge and challenge.lock_at else None})


def participant(user):
    return {"user_id": user.id, "display_name": user.first_name, "username": user.username,
        "avatar_url": user.avatar_url, "profile_url": f"/managers/{user.id}"}


def audit(db, challenge, actor, action, details):
    db.add(ChallengeAudit(challenge_id=challenge.id, actor_id=actor, action=action, at=utcnow(), details=json.loads(json.dumps(details, default=str))))


def ensure_round(db, season, week):
    row = db.query(ChallengeRound).filter_by(season=season, week=week).one_or_none()
    if row is None:
        try:
            with db.begin_nested():
                row = ChallengeRound(season=season, week=week, next_rollover_at=matchup_display_rollover_at(season, week))
                db.add(row)
                db.flush()
                for kind in KINDS:
                    db.add(WeeklyChallenge(round_id=row.id, kind=kind))
                db.flush()
        except IntegrityError:
            row = db.query(ChallengeRound).filter_by(season=season, week=week).one()
    return row


def challenge_or_404(db, challenge_id, *, lock=False):
    query = db.query(WeeklyChallenge).filter_by(id=challenge_id)
    row = (query.with_for_update() if lock else query).populate_existing().one_or_none()
    if row is None:
        fail("NOT_FOUND", "Challenge not found.", 404)
    return row


def slate_rows(db, c):
    return db.query(ChallengeSlateGame).filter_by(challenge_id=c.id).order_by(ChallengeSlateGame.game_id).all()


def games_for(db, c):
    return db.query(Game).join(ChallengeSlateGame, ChallengeSlateGame.game_id == Game.id).filter(ChallengeSlateGame.challenge_id == c.id).order_by(Game.id).all()


def game_read(g):
    return {"id": g.id, "home_team": g.home_team, "away_team": g.away_team, "start_date": aware(g.start_date) if g.start_date else None,
        "status": g.schedule_status, "home_points": g.home_points, "away_points": g.away_points}


def effective_lock(c, games):
    # Schedule corrections may shorten a deadline, never extend/reopen one.
    times = [aware(c.lock_at)] if c.lock_at else []
    times += [aware(g.start_date) - timedelta(minutes=5) for g in games if g.start_date]
    return min(times) if times else None


def reconcile_lock(db, c, games, now):
    if c.status in {"draft", "canceled"}:
        return
    deadline = effective_lock(c, games)
    if deadline and (c.lock_at is None or deadline < aware(c.lock_at)):
        c.lock_at = deadline
    begun = any(not g.start_date or (g.schedule_status or "").lower() not in UNSTARTED or aware(g.start_date) <= now for g in games)
    all_void = bool(games) and all(result_state(g, db.get(ChallengeRound, c.round_id), now) == "void" for g in games)
    if c.locked_at is None and ((deadline and now >= deadline) or begun or all_void):
        c.locked_at = now
        db.add(c)


def challenge_state(c, round_, games, now):
    if c.status == "canceled": return "Canceled"
    if c.status == "draft" or (round_.season, round_.week) > (settings.current_season_year, competition_week(settings.current_season_year, now)):
        return "Upcoming"
    if c.status in {"final", "no_contest"}: return "Closed — Final"
    deadline = effective_lock(c, games)
    if deadline and now < deadline and (round_.season, round_.week) < (settings.current_season_year, competition_week(settings.current_season_year, now)):
        return "Closed — Entries ended"
    if c.locked_at is None and deadline and now < deadline and all((g.schedule_status or "").lower() in UNSTARTED and g.start_date and aware(g.start_date) > now for g in games):
        return "Open"
    return "Closed — Results Processing" if all(result_state(g, round_, now) in {"final", "void"} for g in games) else "Closed — Live"


def assert_open(db, c):
    now = utcnow()  # Read AFTER obtaining the row lock, never request arrival time.
    round_ = db.get(ChallengeRound, c.round_id)
    games = games_for(db, c)
    snapshots = {x.game_id: x.snapshot for x in slate_rows(db, c)}
    if c.status != "draft" and any(not game_identity_matches(g, snapshots.get(g.id, {}), round_) for g in games):
        fail("TEMPORARY_DATA_FAILURE", "The published schedule needs verification. Please try again later.", 503, c)
    reconcile_lock(db, c, games, now)
    if c.status == "draft": fail("NOT_PUBLISHED", "This challenge is not published yet.", challenge=c)
    if (round_.season, round_.week) != (settings.current_season_year, competition_week(settings.current_season_year, now)):
        fail("CHALLENGE_CLOSED", "This round is not the current competition week.", challenge=c)
    if challenge_state(c, round_, games, now) != "Open":
        # A rejected mutation must not save partially edited selections. Persist
        # only the irreversible close, including provider-started early games.
        cid, deadline = c.id, c.lock_at
        db.rollback()
        c = challenge_or_404(db, cid, lock=True)
        if deadline and (c.lock_at is None or aware(deadline) < aware(c.lock_at)):
            c.lock_at = deadline
        c.locked_at = c.locked_at or now
        db.commit()
        if c.lock_at and now >= aware(c.lock_at):
            fail("DEADLINE_PASSED", "Closed. Entries and invitations lock five minutes before the first game.", challenge=c)
        fail("CHALLENGE_CLOSED", "Closed. This published slate no longer accepts entry changes.", challenge=c)
    return round_, games


def entry_for(db, c, user_id):
    return db.query(ChallengeEntry).filter_by(challenge_id=c.id, user_id=user_id).one_or_none()


def read_challenge(db, c, user, *, admin=False, now=None, include_details=True):
    now = now or utcnow()
    r = db.get(ChallengeRound, c.round_id)
    games = games_for(db, c)
    reconcile_lock(db, c, games, now)
    public = admin or c.published_at is not None
    # Draft configurations, pool and source games never leak to ordinary entrants.
    snapshots = [x.snapshot for x in slate_rows(db, c)] if public and include_details else []
    current = {g.id: g for g in games}
    display_games = [{**x, "status": current[x["id"]].schedule_status,
        "home_points": current[x["id"]].home_points, "away_points": current[x["id"]].away_points} for x in snapshots]
    config = c.config if public else {}
    return {"sponsor": weekly_challenge_sponsor(season=r.season, week=r.week), "id": c.id, "round_id": r.id, "kind": c.kind, "name": KINDS[c.kind],
        "state": challenge_state(c, r, games, now), "settlement_status": c.status, "version": c.version, "rules_version": c.rules_version,
        "rules": RULES[c.kind] + DISRUPTION_RULE, "lock_at": c.lock_at if public else None,
        "server_now": now, "published_at": c.published_at,
        "scoring_version": config.get("scoring_version"), "scoring_rules": config.get("scoring_rules"),
        "games": display_games, "players": [{**x.snapshot, "image_url": x.snapshot.get("image_url") if settings.player_headshots_enabled else None} for x in db.query(ChallengePoolPlayer).filter_by(challenge_id=c.id).order_by(ChallengePoolPlayer.player_id).all()] if public and include_details else [],
        "featured_game_id": config.get("featured_game_id"), "underdogs": config.get("underdogs", []),
        "entry": entry_for(db, c, user.id), "cancellation_reason": c.cancellation_reason,
        "draft_config": {"game_ids": c.config.get("game_ids", []), "player_ids": c.config.get("player_ids", []), "featured_game_id": c.config.get("featured_game_id"), "underdogs": c.config.get("underdogs", [])} if admin else None}


def read_round(db, row, user, *, admin=False):
    now = utcnow()
    challenges = [read_challenge(db, c, user, now=now, admin=admin, include_details=False) for c in db.query(WeeklyChallenge).filter_by(round_id=row.id).order_by(WeeklyChallenge.id)]
    states = [c["state"] for c in challenges]
    return {"sponsor": weekly_challenge_sponsor(season=row.season, week=row.week), "id": row.id, "season": row.season, "week": row.week, "next_rollover_at": row.next_rollover_at, "server_now": now,
        "state": "Open" if "Open" in states else "Upcoming" if all(x == "Upcoming" for x in states) else "Closed", "challenges": challenges}


def canonical_slate(db, season, week):
    games = db.query(Game).filter(Game.season == season, Game.week == week, Game.season_type == "regular").order_by(Game.start_date, Game.id).all()
    # Reuse canonical alias/placeholder handling. Ambiguous games are not guessed.
    by_school = fantasy_games_by_school(db, season=season, week=week, games=games)
    game_ids = {g.id for g in by_school.values() if g is not None}
    games = [g for g in games if g.id in game_ids]
    return games, by_school


def catalog(db, season, week):
    games, by_school = canonical_slate(db, season, week)
    players = []
    for p in db.query(Player).filter(canonical_fantasy_player_filter(season), season_eligible_player_filter(season), Player.position.in_(("QB", "RB", "WR", "TE"))).order_by(Player.name, Player.id):
        matched = by_school.get(school_key(p.school))
        if matched is not None:
            players.append({"id": p.id, "game_id": matched.id, "name": p.name, "school": p.school, "position": p.position.upper(),
                "image_url": (p.image_url or p.espn_headshot_url) if settings.player_headshots_enabled else None})
    return {"season": season, "week": week, "games": [game_read(g) for g in games], "players": players}


def validate_config(db, c, config):
    r = db.get(ChallengeRound, c.round_id)
    issues = []
    ids = config.get("game_ids", [])
    games = db.query(Game).filter(Game.id.in_(ids)).all()
    now = utcnow()
    if not ids or len(set(ids)) != len(ids) or len(games) != len(ids): issues.append("Select distinct, existing games.")
    eligible_ids = {g.id for g in canonical_slate(db, r.season, r.week)[0]}
    if not set(ids).issubset(eligible_ids) or len({g.external_id for g in games}) != len(games):
        issues.append("Choose distinct provider events from the canonical weekly game catalog; resolve ambiguous or duplicate schedules first.")
    if c.kind == "slate12" and len(ids) != 12: issues.append("Slate 12 requires exactly 12 games.")
    if c.kind == "duels" and len(ids) != 5: issues.append("Rivalry Duels requires exactly 5 games.")
    if any(g.season != r.season or g.week != r.week or g.season_type != "regular" or not g.external_id or g.external_id.startswith(("sheet-", "sealed-")) or not g.start_date or
        (g.schedule_status or "").lower() not in SCHEDULED or aware(g.start_date) <= now + timedelta(minutes=5) or aware(g.start_date) >= aware(r.next_rollover_at) or
        any((t or "").strip().upper() in {"", "TBD", "BYE"} for t in (g.home_team, g.away_team)) for g in games):
        issues.append("Every game needs an authoritative same-week identity, future kickoff and scheduled status.")
    if c.kind == "slate12" and config.get("featured_game_id") not in ids: issues.append("Choose a featured tiebreaker game in the slate.")
    dogs = config.get("underdogs", [])
    if c.kind == "upset":
        game_map = {g.id: g for g in games}
        if len(dogs) < 3 or len({d["game_id"] for d in dogs}) != len(dogs): issues.append("Publish underdogs from at least 3 different games, one designated team per game.")
        if {d["game_id"] for d in dogs} != set(ids): issues.append("Every game in the Upset Hunter slate must have one explicitly designated underdog.")
        if any(d["game_id"] not in game_map or d["team"] not in (game_map[d["game_id"]].home_team, game_map[d["game_id"]].away_team) or not 1 <= d["points"] <= 5 for d in dogs): issues.append("Underdog teams must belong to their game with fixed difficulty 1–5.")
    elif dogs: issues.append("Underdogs are only valid for Upset Hunter.")
    if c.kind != "slate12" and config.get("featured_game_id") is not None: issues.append("Only Slate 12 has a featured-game tiebreaker.")
    if c.kind == "fantasy5":
        available = {p["id"]: p for p in catalog(db, r.season, r.week)["players"] if p["game_id"] in ids}
        pids = config.get("player_ids", [])
        pool = [available[p] for p in pids if p in available]
        if {p["game_id"] for p in pool} != set(ids): issues.append("Every Fantasy Five slate game must supply at least one eligible published player.")
        if len(pids) != len(set(pids)) or len(pool) != len(pids): issues.append("Player pool must contain distinct canonical approved players in the selected games.")
        if len(pool) < 5 or not {"QB", "RB", "WR", "TE"}.issubset({p["position"] for p in pool}) or sum(p["position"] in {"RB", "WR", "TE"} for p in pool) < 4:
            issues.append("Player pool cannot fill QB, RB, WR, TE and a distinct FLEX.")
        try: get_scoring_rules()
        except ValueError: issues.append("Canonical CFFB scoring configuration is invalid; publishing is blocked.")
    elif config.get("player_ids"): issues.append("Player pools are only valid for Fantasy Five.")
    return issues, games


def configure(db, c, payload: ChallengeConfig, actor):
    if c.version != payload.expected_version: fail("VERSION_CONFLICT", "Configuration changed. Reload before saving.", challenge=c)
    if c.status != "draft": fail("IMMUTABLE_RULES", "Published rules and slates are frozen. Cancel this challenge instead.", challenge=c)
    c.config = payload.model_dump(exclude={"expected_version"})
    c.version += 1
    audit(db, c, actor, "configure", {"version": c.version, "config": c.config})
    db.commit()


def publish(db, c, expected_version, actor):
    if c.version != expected_version: fail("VERSION_CONFLICT", "Configuration changed. Reload before publishing.", challenge=c)
    if c.status != "draft": fail("IMMUTABLE_RULES", "This challenge is already published or canceled.", challenge=c)
    issues, games = validate_config(db, c, c.config)
    if issues: fail("INVALID_CONFIGURATION", " ".join(issues), 422, c)
    r = db.get(ChallengeRound, c.round_id)
    if (r.season, r.week) < (settings.current_season_year, competition_week(settings.current_season_year, utcnow())):
        fail("CHALLENGE_CLOSED", "Cannot publish a historical round.", challenge=c)
    config = dict(c.config)
    if c.kind == "fantasy5": config.update(scoring_rules=get_scoring_rules(), scoring_version=CALCULATION_VERSION)
    for g in games:
        db.add(ChallengeSlateGame(challenge_id=c.id, game_id=g.id, snapshot={"id": g.id, "external_id": g.external_id, "home_team": g.home_team, "away_team": g.away_team, "start_date": aware(g.start_date).isoformat(), "status": g.schedule_status}))
    if c.kind == "fantasy5":
        wanted = set(config["player_ids"])
        for p in catalog(db, r.season, r.week)["players"]:
            if p["id"] in wanted: db.add(ChallengePoolPlayer(challenge_id=c.id, player_id=p["id"], game_id=p["game_id"], snapshot=p))
    c.config = config
    c.status = "published"
    c.lock_at = min(aware(g.start_date) for g in games) - timedelta(minutes=5)
    c.published_at = utcnow()
    c.version += 1
    audit(db, c, actor, "publish", {"version": c.version, "rules_version": c.rules_version, "config": config, "lock_at": c.lock_at.isoformat()})
    db.commit()


def validate_entry(db, c, payload, complete):
    selections = [s.model_dump(exclude_none=True) for s in payload.selections]
    if c.kind == "fantasy5":
        pool = {p.player_id: p.snapshot for p in db.query(ChallengePoolPlayer).filter_by(challenge_id=c.id)}
        ids = [s.get("player_id") for s in selections]
        slots = [s.get("slot") for s in selections]
        if len(set(ids)) != len(ids) or len(set(slots)) != len(slots): fail("INVALID_ENTRY", "Choose distinct players and slots.", 422, c)
        if any(set(s) != {"player_id", "slot"} or s["player_id"] not in pool or (pool[s["player_id"]]["position"] not in ({"RB", "WR", "TE"} if s["slot"] == "FLEX" else {s["slot"]})) for s in selections):
            fail("INVALID_ENTRY", "Player is outside the published pool or in an invalid slot.", 422, c)
        if complete and set(slots) != {"QB", "RB", "WR", "TE", "FLEX"}: fail("INCOMPLETE_ENTRY", "Fill all five lineup slots.", 422, c)
    else:
        games = {row.game_id: row.snapshot for row in slate_rows(db, c)}
        ids = [s.get("game_id") for s in selections]
        if len(set(ids)) != len(ids): fail("INVALID_ENTRY", "Each selection must use a different game.", 422, c)
        if any(set(s) != {"game_id", "team"} or s["game_id"] not in games or s["team"] not in (games[s["game_id"]]["home_team"], games[s["game_id"]]["away_team"]) for s in selections):
            fail("INVALID_ENTRY", "Pick a published team in its own game.", 422, c)
        count = {"slate12": 12, "upset": 3, "lock": 1, "duels": 5}[c.kind]
        if len(selections) > count or (complete and len(selections) != count): fail("INCOMPLETE_ENTRY", f"Choose exactly {count} selections.", 422, c)
        if c.kind == "upset":
            dogs = {(d["game_id"], d["team"]) for d in c.config["underdogs"]}
            if any((s["game_id"], s["team"]) not in dogs for s in selections): fail("INVALID_ENTRY", "Only published underdogs are eligible.", 422, c)
    if c.kind == "slate12" and complete and payload.tiebreaker is None: fail("INCOMPLETE_ENTRY", "Predict the featured game's combined final score.", 422, c)
    if c.kind != "slate12" and payload.tiebreaker is not None: fail("INVALID_ENTRY", "This format has no tiebreaker.", 422, c)
    return selections


def save_entry(db, c, user, payload: EntryWrite):
    assert_open(db, c)
    selections = validate_entry(db, c, payload, payload.submit)
    entry = entry_for(db, c, user.id)
    if (entry.revision if entry else 0) != payload.expected_revision:
        fail("VERSION_CONFLICT", "Your entry changed on another screen. Reload the saved entry before editing.", challenge=c)
    if entry is None:
        entry = ChallengeEntry(challenge_id=c.id, user_id=user.id, revision=0)
        db.add(entry)
    # Once official, only an explicit submission changes ranked picks. A
    # "Save Draft" action must never silently replace an official lineup.
    if entry.status == "submitted" and not payload.submit:
        fail("INVALID_ENTRY", "This entry is already official. Submit an update to change its ranked selections.", 422, c)
    entry.selections = selections
    entry.tiebreaker = payload.tiebreaker
    entry.revision += 1
    entry.status = "submitted" if payload.submit or entry.status == "submitted" else "draft"
    entry.submitted_at = utcnow() if entry.status == "submitted" else None
    assert_open(db, c)
    db.commit()
    db.refresh(entry)
    return entry


def invite_duel(db, c, user, invitee_id):
    assert_open(db, c)
    if c.kind != "duels": fail("INVALID_ENTRY", "Invitations belong to Rivalry Duels only.", 422, c)
    target = db.get(User, invitee_id)
    if invitee_id == user.id or target is None or not target.is_active: fail("INVALID_DUEL", "Choose a different active manager.", 422, c)
    if not (e := entry_for(db, c, user.id)) or e.status != "submitted": fail("INCOMPLETE_ENTRY", "Submit your five picks before inviting a manager.", 422, c)
    ids = sorted((user.id, invitee_id))
    if db.query(ChallengeDuelSeat).filter(ChallengeDuelSeat.challenge_id == c.id, ChallengeDuelSeat.user_id.in_(ids)).first(): fail("DUPLICATE_DUEL", "One of these accounts already has an accepted duel.", challenge=c)
    if db.query(ChallengeDuel).filter_by(challenge_id=c.id, low_user_id=ids[0], high_user_id=ids[1]).first(): fail("DUPLICATE_DUEL", "An invitation for this pairing already exists.", challenge=c)
    d = ChallengeDuel(challenge_id=c.id, inviter_id=user.id, invitee_id=invitee_id, low_user_id=ids[0], high_user_id=ids[1])
    db.add(d)
    assert_open(db, c)
    db.commit()
    return d


def respond_duel(db, c, user, duel_id, accept):
    assert_open(db, c)
    d = db.query(ChallengeDuel).filter_by(id=duel_id, challenge_id=c.id).one_or_none()
    if not d or d.invitee_id != user.id: fail("UNAUTHORIZED", "Only the invited manager can respond.", 403, c)
    if d.status != "pending": fail("VERSION_CONFLICT", "This invitation has already been answered.", challenge=c)
    if accept:
        # Challenge lock serializes cross-role accepts; the unique seat constraint
        # is the database's independent last line of defense.
        ids = [d.low_user_id, d.high_user_id]
        users = db.query(User).filter(User.id.in_(ids), User.is_active.is_(True)).all()
        entries = db.query(ChallengeEntry).filter(ChallengeEntry.challenge_id == c.id, ChallengeEntry.user_id.in_(ids), ChallengeEntry.status == "submitted").all()
        if len(users) != 2 or len(entries) != 2: fail("INCOMPLETE_ENTRY", "Both managers must submit complete entries before accepting.", 422, c)
        if db.query(ChallengeDuelSeat).filter(ChallengeDuelSeat.challenge_id == c.id, ChallengeDuelSeat.user_id.in_(ids)).first(): fail("DUPLICATE_DUEL", "Each manager can accept only one duel this week.", challenge=c)
        for uid in ids: db.add(ChallengeDuelSeat(challenge_id=c.id, duel_id=d.id, user_id=uid))
        d.accepted_at = utcnow()
    d.status = "accepted" if accept else "declined"
    assert_open(db, c)
    db.commit()
    return d


def read_duels(db, c, user):
    rows = db.query(ChallengeDuel).filter(ChallengeDuel.challenge_id == c.id, or_(ChallengeDuel.inviter_id == user.id, ChallengeDuel.invitee_id == user.id)).order_by(ChallengeDuel.id).all()
    users = {u.id: u for u in db.query(User).filter(User.id.in_({x for d in rows for x in (d.inviter_id, d.invitee_id)}))}
    return [{"id": d.id, "challenge_id": c.id, "inviter": participant(users[d.inviter_id]), "invitee": participant(users[d.invitee_id]), "status": d.status, "outcome": d.outcome} for d in rows]


def result_state(game, round_, now):
    status = (game.schedule_status or "").lower()
    if status in VOID: return "void"
    if game.start_date and aware(game.start_date) >= aware(round_.next_rollover_at): return "void"
    if status == "postponed" and now >= aware(round_.next_rollover_at): return "void"
    if status in FINAL and game.home_points is not None and game.away_points is not None: return "final"
    return "pending"


def game_identity_matches(game, snapshot, round_):
    return (snapshot.get("home_team") == game.home_team and snapshot.get("away_team") == game.away_team
        and snapshot.get("external_id") == game.external_id and game.season == round_.season
        and game.week == round_.week and game.season_type == "regular")


def settle(db, c, *, actor=None, reason="Scheduled settlement", force=False):
    if c.status == "draft": return "upcoming"
    r = db.get(ChallengeRound, c.round_id)
    now = utcnow()
    games = games_for(db, c)
    reconcile_lock(db, c, games, now)
    if not c.locked_at and c.status != "canceled":
        c.last_scored_at = now
        db.commit()
        return "open"
    entries = db.query(ChallengeEntry).filter_by(challenge_id=c.id, status="submitted").order_by(ChallengeEntry.id).all()
    prior = db.query(ChallengeAudit).filter(ChallengeAudit.challenge_id == c.id, ChallengeAudit.action.in_(("score", "correction"))).order_by(ChallengeAudit.id.desc()).first()
    # The immutable settlement ledger remembers rollover voids. A later final
    # response (or a repaired kickoff) cannot resurrect an excluded late game.
    rollover_voids = set(prior.details.get("rollover_void_game_ids", [])) if prior else set()
    rollover_voids.update(g.id for g in games if (g.start_date and aware(g.start_date) >= aware(r.next_rollover_at)) or ((g.schedule_status or "").lower() == "postponed" and now >= aware(r.next_rollover_at)))
    states = {g.id: "void" if g.id in rollover_voids else result_state(g, r, now) for g in games}
    void_all = bool(games) and all(s == "void" for s in states.values())
    resolved = bool(games) and all(s in {"void", "final"} for s in states.values())
    snapshots = {g.game_id: g.snapshot for g in slate_rows(db, c)}
    # A provider identity change is a data problem, not a new opponent quietly
    # substituted into a published slate.
    identity_ok = all(game_identity_matches(g, snapshots[g.id], r) for g in games)
    engine_supported = c.kind != "fantasy5" or c.config.get("scoring_version") == CALCULATION_VERSION
    if (not identity_ok or not engine_supported) and c.status != "canceled": resolved = False
    game_map = {g.id: g for g in games}
    pool = {p.player_id: p for p in db.query(ChallengePoolPlayer).filter_by(challenge_id=c.id)}
    chosen = {s["player_id"] for e in entries for s in e.selections if "player_id" in s}
    stats = {(s.player_id, s.game_id): s for s in db.query(PlayerGameStat).filter(PlayerGameStat.player_id.in_(chosen), PlayerGameStat.game_id.in_(game_map), PlayerGameStat.season == r.season, PlayerGameStat.source == "espn_final_boxscore")}
    nonparticipants = confirmed_nonparticipant_ids(db, season=r.season, week=r.week, player_ids=chosen) if c.kind == "fantasy5" else set()
    duels = db.query(ChallengeDuel).filter_by(challenge_id=c.id, status="accepted").order_by(ChallengeDuel.id).all()
    source = {"config": c.config, "rules_version": c.rules_version, "games": [(g.id,g.external_id,g.season,g.week,g.season_type,g.schedule_status,g.start_date,g.home_team,g.away_team,g.home_points,g.away_points,states[g.id]) for g in games], "entries": [(e.id,e.revision,e.selections,e.tiebreaker) for e in entries],
        "duels": [(d.id,d.inviter_id,d.invitee_id,d.accepted_at) for d in duels], "rollover_void_game_ids": sorted(rollover_voids),
        "stats": [(s.player_id,s.game_id,s.stats) for s in sorted(stats.values(), key=lambda s:s.id)], "confirmed_nonparticipants": sorted(nonparticipants), "engine_version": CALCULATION_VERSION if c.kind == "fantasy5" else None, "canceled": c.status == "canceled"}
    fingerprint = hashlib.sha256(json.dumps(source, sort_keys=True, default=str).encode()).hexdigest()
    c.last_scored_at = now
    if fingerprint == c.source_hash and not force:
        db.commit()
        return c.status
    raw = {}
    errors = {}
    dogs = {(d["game_id"], d["team"]): d["points"] for d in c.config.get("underdogs", [])}
    for e in entries:
        total = Decimal(0)
        missing = False
        for pick in e.selections:
            if c.kind == "fantasy5":
                p = pool[pick["player_id"]]
                g = game_map[p.game_id]
                if states[g.id] == "void": continue
                fact = stats.get((p.player_id, g.id))
                value = points_from_verified_stats(fact.stats, position=p.snapshot["position"], rules=c.config["scoring_rules"]) if fact and fact.week == g.week else None
                if fact is None and p.player_id in nonparticipants and states[g.id] == "final": value = 0.0
                # Missing box scores are never silently turned into DNP/zero.
                if value is None: missing = True
                else: total += Decimal(str(value))
            else:
                g = game_map[pick["game_id"]]
                if states[g.id] != "final": continue
                won = (pick["team"] == g.home_team and g.home_points > g.away_points) or (pick["team"] == g.away_team and g.away_points > g.home_points)
                if won: total += dogs[(g.id, pick["team"])] if c.kind == "upset" else 5 if c.kind == "lock" else 1
        raw[e.id] = None if missing else total
        featured = game_map.get(c.config.get("featured_game_id"))
        errors[e.id] = abs(e.tiebreaker - featured.home_points - featured.away_points) if featured and states[featured.id] == "final" and e.tiebreaker is not None else None
    resolved = resolved and all(v is not None for v in raw.values())
    no_contest = void_all or c.status == "canceled"
    final = resolved or no_contest
    ordered = sorted(entries, key=lambda e: (-(raw[e.id] or 0), errors[e.id] if errors[e.id] is not None else 0, e.user_id))
    ranks = {}
    previous = None
    for index, e in enumerate(ordered, 1):
        key = (raw[e.id], errors[e.id])
        if key != previous or index == 1: rank = index
        ranks[e.id] = rank
        previous = key
    points = {e.id: 0 if no_contest or not final else max(0, 11-ranks[e.id]) if c.kind == "fantasy5" else int(raw[e.id] or 0) for e in entries}
    if c.kind == "duels":
        points = dict.fromkeys(points, 0)
        by_user = {e.user_id:e for e in entries}
        for d in duels:
            a, b = by_user.get(d.inviter_id), by_user.get(d.invitee_id)
            if no_contest or not a or not b: d.outcome = "no_contest" if final else None
            elif final:
                if raw[a.id] == raw[b.id]: points[a.id] = points[b.id] = 2; d.outcome = "draw"
                else:
                    winner = a if raw[a.id] > raw[b.id] else b
                    points[winner.id] = 5
                    d.outcome = f"winner:{winner.user_id}"
    existing_scores = {s.entry_id:s for s in db.query(ChallengeScore).filter(ChallengeScore.entry_id.in_([e.id for e in entries]))}
    existing_awards = {a.entry_id:a for a in db.query(ChallengeAward).filter(ChallengeAward.entry_id.in_([e.id for e in entries]))}
    old_awards = {eid:a.points for eid,a in existing_awards.items()}
    for e in entries:
        score = existing_scores.get(e.id) or ChallengeScore(entry_id=e.id)
        score.raw_points = raw[e.id] if final and not no_contest else None
        score.tiebreaker_error = errors[e.id] if final and not no_contest else None
        score.rank = ranks[e.id] if final and not no_contest else None
        score.status = "no_contest" if no_contest else "final" if final else "processing"
        score.source_hash = fingerprint
        score.details = {"game_states": states, "scoring_version": c.config.get("scoring_version"), "identity_verified": identity_ok}
        db.add(score)
        award = existing_awards.get(e.id)
        if final:
            if award is None: award = ChallengeAward(entry_id=e.id, round_id=r.id, user_id=e.user_id, points=points[e.id], revision=0)
            award.points = points[e.id]
            award.source_hash = fingerprint
            award.revision += 1
            db.add(award)
        elif award is not None:
            # A correction withdrawing authoritative finality withdraws the old
            # award from standings until data can be certified again.
            award.points = 0
            award.source_hash = fingerprint
            award.revision += 1
    c.source_hash = fingerprint
    if c.status != "canceled": c.status = "no_contest" if no_contest else "final" if final else "processing"
    c.finalized_at = now if final else None
    winners = {e.user_id for e in entries if final and not no_contest and points[e.id] > 0 and ranks[e.id] == 1}
    if c.kind == "duels": winners = {e.user_id for e in entries if points[e.id] == 5}
    code = f"{c.kind}_winner"
    badges = {b.user_id:b for b in db.query(ChallengeRecognition).filter_by(round_id=r.id, code=code)}
    for uid in set(badges) | winners:
        badge = badges.get(uid) or ChallengeRecognition(round_id=r.id, user_id=uid, code=code)
        badge.active = uid in winners
        db.add(badge)
    audit(db, c, actor, "correction" if existing_scores else "score", {"reason": reason, "source_hash": fingerprint, "status": c.status, "previous_awards": old_awards, "awards": points if final else {}, "rollover_void_game_ids": sorted(rollover_voids), "source": source})
    db.flush()
    refresh_weekly_recognition(db, r)
    db.commit()
    return c.status


def refresh_weekly_recognition(db, round_):
    statuses = [s for (s,) in db.query(WeeklyChallenge.status).filter_by(round_id=round_.id)]
    totals = db.query(ChallengeAward.user_id, func.sum(ChallengeAward.points)).filter_by(round_id=round_.id).group_by(ChallengeAward.user_id).all()
    ready = len(statuses) == 5 and all(s in {"final", "no_contest", "canceled"} for s in statuses)
    high = max((points for _, points in totals), default=0)
    winners = {uid for uid, points in totals if ready and high > 0 and points == high}
    badges = {b.user_id:b for b in db.query(ChallengeRecognition).filter_by(round_id=round_.id, code="weekly_winner")}
    for uid in set(badges) | winners:
        badge = badges.get(uid) or ChallengeRecognition(round_id=round_.id, user_id=uid, code="weekly_winner")
        badge.active = uid in winners
        db.add(badge)


def cancel(db, c, actor, expected_version, reason):
    if c.version != expected_version: fail("VERSION_CONFLICT", "Configuration changed. Reload before canceling.", challenge=c)
    c.status = "canceled"
    c.cancellation_reason = reason
    c.version += 1
    audit(db, c, actor, "cancel", {"reason": reason})
    settle(db, c, actor=actor, reason=reason, force=True)


def leaderboard(db, user, *, season, round_id=None):
    totals = (select(ChallengeAward.user_id.label("user_id"), func.sum(ChallengeAward.points).label("points"))
        .join(ChallengeRound, ChallengeRound.id == ChallengeAward.round_id)
        .join(ChallengeEntry, ChallengeEntry.id == ChallengeAward.entry_id)
        .join(WeeklyChallenge, WeeklyChallenge.id == ChallengeEntry.challenge_id)
        .join(User, User.id == ChallengeAward.user_id)
        .where(ChallengeRound.season == season, WeeklyChallenge.status.in_(("final", "no_contest", "canceled")), User.is_active.is_(True)))
    if round_id is not None: totals = totals.where(ChallengeAward.round_id == round_id)
    totals = totals.group_by(ChallengeAward.user_id).subquery()
    ranked = select(totals.c.user_id, totals.c.points, func.rank().over(order_by=totals.c.points.desc()).label("rank")).subquery()
    def row_read(row):
        u, points, rank = row
        return {**participant(u), "points": int(points), "rank": int(rank)}
    query = db.query(User, ranked.c.points, ranked.c.rank).join(ranked, ranked.c.user_id == User.id)
    top = [row_read(x) for x in query.order_by(ranked.c.rank, User.id).limit(10)]
    mine = query.filter(User.id == user.id).first()
    unsettled = db.query(WeeklyChallenge.id).join(ChallengeRound).filter(ChallengeRound.season == season, WeeklyChallenge.status.notin_(("final", "no_contest", "canceled")))
    if round_id is not None: unsettled = unsettled.filter(ChallengeRound.id == round_id)
    return {"season": season, "week": db.get(ChallengeRound, round_id).week if round_id else None, "round_id": round_id, "provisional": unsettled.first() is not None if round_id else False, "data": top, "your_rank": row_read(mine) if mine and user.id not in [x["user_id"] for x in top] else None}


def results(db, c, user, limit, offset):
    r = db.get(ChallengeRound, c.round_id)
    deadline = effective_lock(c, games_for(db, c))
    closed = deadline is not None and utcnow() >= deadline
    query = db.query(ChallengeEntry, User, ChallengeScore, ChallengeAward).join(User, User.id == ChallengeEntry.user_id).outerjoin(ChallengeScore, ChallengeScore.entry_id == ChallengeEntry.id).outerjoin(ChallengeAward, ChallengeAward.entry_id == ChallengeEntry.id).filter(ChallengeEntry.challenge_id == c.id, ChallengeEntry.status == "submitted")
    if not closed: query = query.filter(ChallengeEntry.user_id == user.id)
    count = query.count()
    def result_read(row):
        e, u, s, a = row
        return {"participant": participant(u), "entry_id": e.id, "raw_points": float(s.raw_points) if s and s.raw_points is not None else None,
            "challenge_points": a.points if a and s and s.status in {"final", "no_contest"} else None, "rank": s.rank if s else None,
            "status": s.status if s else "pending", "tiebreaker_error": s.tiebreaker_error if s else None,
            "selections": e.selections if closed or e.user_id == user.id else None}
    data = [result_read(row) for row in query.order_by(ChallengeScore.rank.asc().nullslast(), User.id).limit(limit).offset(offset)]
    mine = query.filter(ChallengeEntry.user_id == user.id).first()
    return {"challenge_id": c.id, "state": challenge_state(c, r, games_for(db, c), utcnow()), "data": data, "total": count, "limit": limit, "offset": offset, "my_result": result_read(mine) if mine else None}


def process_weekly_challenges_once(db):
    current = ensure_round(db, settings.current_season_year, competition_week(settings.current_season_year, utcnow()))
    db.commit()
    now = utcnow()
    candidates = db.query(WeeklyChallenge.id).filter(WeeklyChallenge.status.notin_(("draft", "canceled")), or_(WeeklyChallenge.last_scored_at.is_(None), WeeklyChallenge.last_scored_at < now-timedelta(seconds=60))).order_by(WeeklyChallenge.last_scored_at.asc().nullsfirst(), WeeklyChallenge.id).limit(20).all()
    count = 0
    for (cid,) in candidates:
        c = db.query(WeeklyChallenge).filter_by(id=cid).with_for_update(skip_locked=True).populate_existing().one_or_none()
        if c and (c.last_scored_at is None or aware(c.last_scored_at) < now-timedelta(seconds=60)):
            settle(db, c)
            count += 1
        else: db.rollback()
    return {"round_id": current.id, "checked": count}
