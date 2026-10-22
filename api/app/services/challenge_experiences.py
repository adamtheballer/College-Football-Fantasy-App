"""Additional modes on the canonical WeeklyChallenge/ChallengeEntry ledger.

All scores use canonical game facts and CFFB's existing fantasy calculation.
Mode raw totals never enter the five-format achievement championship.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from sqlalchemy import func, case, select, and_
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from collegefootballfantasy_api.app.models.weekly_challenge import (
    WeeklyChallenge,
    ChallengeRound,
    ChallengeEntry,
    ChallengeScore,
    ChallengeSlateGame,
    ChallengePoolPlayer,
    ChallengeAudit,
)
from collegefootballfantasy_api.app.models.challenge_experience import (
    ChallengeCreator,
    ChallengeExperience,
    ChallengeSalary,
    ChallengeCreatorPick,
    ChallengeFanMembership,
    ChallengeEntrySchool,
    ChallengeSurvivorSeries,
    ChallengeSurvivorEnrollment,
    ChallengeSurvivorPick,
    ChallengeGameDecision,
    ChallengeEvent,
)
from collegefootballfantasy_api.app.models.college_team import CollegeTeam
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.challenge_experience import ExperienceRead
from collegefootballfantasy_api.app.services.player_pool_filters import (
    normalize_league_conference_codes,
)
from collegefootballfantasy_api.app.services.fantasy_game_selection import school_key

KINDS = {
    "fanwars": "College Football Fan Wars",
    "millionaire": "Fantasy Millionaire",
    "creator": "Beat the Creator",
    "survivor": "Last Fan Standing",
}
DESCRIPTIONS = {
    "fanwars": "Represent Your School",
    "millionaire": "Build the Ultimate $100 Lineup",
    "creator": "Can You Outpick the Experts?",
    "survivor": "One Pick. Survive Another Week.",
}
SLOTS = ("QB", "RB", "WR1", "WR2", "TE", "FLEX")
RULES = {
    "fanwars": "Represent one Power Four school for the entire competition week. Each correct eligible pick earns {correct_points} Fan Points; losses earn 0. Each game locks at its first published or corrected kickoff, whichever is earlier, or when officially started. One pick per account per game. Fan Accuracy is total correct / resolved nonvoid picks, with at least {minimum_fans} active fans per school; other schools are provisional. Fan Power is total earned points. Pending and void games are excluded from accuracy. Allegiance and weekly conference membership are frozen. All-void slates are no contest.",
    "millionaire": "Free virtual salary-cap competition: $100 credits, no entry fee or cash payout. Select six distinct players: QB, RB, WR, WR, TE, RB/WR/TE FLEX. Published salary snapshots are immutable. All lineups lock at the earliest published or corrected kickoff. Existing frozen CFFB fantasy scoring determines totals. Missing stats remain pending; verified nonparticipation earns 0. Canceled games and games postponed beyond weekly rollover are void (0); all-void slates are no contest. Equal fantasy totals share rank. Opposing lineups stay private until lock.",
    "creator": "Pick all 10 winners from the same frozen slate as the authorized creator. Correct predictions earn {correct_points} points and incorrect predictions earn 0. All predictions lock at the earliest published or corrected kickoff. Canceled games and games postponed beyond weekly rollover are void. Unresolved games remain pending. Equal totals tie; final scores classify Beat, Tied, or Creator Won. Creator corrections require an administrator, a published reason, and an audit record. All-void slates are no contest.",
    "survivor": "Join this series before its first global lock. Pick exactly one eligible team each week; a team cannot be reused in this series. Each weekly pick locks at the earliest published or corrected kickoff. Official wins survive; official losses and missed weekly picks eliminate. Ties, cancellations, postponements, forfeits and no-contests stay pending until an administrator confirms a void-and-advance decision after the scoring window. No re-entry after elimination. New users join a new series. Surviving the last configured week produces joint winners when tied. Corrections are audited and may change later eligibility.",
}


def core():
    from collegefootballfantasy_api.app.services import weekly_challenges

    return weekly_challenges


def aware(value):
    return core().aware(value)


def now():
    return core().utcnow()


def fail(code, message, status=409, c=None):
    core().fail(code, message, status, c)


def detail(db, c):
    row = db.get(ChallengeExperience, c.id)
    if row is None:
        fail("NOT_FOUND", "Competition mode configuration not found.", 404, c)
    return row


def creator_read(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "slug",
            "name",
            "description",
            "logo_url",
            "links",
            "authorized",
            "active",
        )
    }


def series_read(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "name",
            "season",
            "start_week",
            "end_week",
            "entry_open_at",
            "first_lock_at",
            "active",
        )
    }


def schools(db):
    result = []
    for t in db.query(CollegeTeam).order_by(CollegeTeam.name):
        try:
            code = normalize_league_conference_codes([t.conference])[0]
        except ValueError:
            continue
        if code != "INDEPENDENT":
            result.append({"id": t.id, "name": t.name, "conference": code})
    return result


def game_deadline(row, g):
    original = datetime.fromisoformat(row.snapshot["start_date"])
    return (
        min(aware(original), aware(g.start_date)) if g.start_date else aware(original)
    )


def locked_games(db, c, games=None):
    games = {g.id: g for g in (games or core().games_for(db, c))}
    locked = set()
    for row in core().slate_rows(db, c):
        g = games[row.game_id]
        if row.locked_at is None and (
            now() >= game_deadline(row, g)
            or (g.schedule_status or "").lower() not in core().UNSTARTED
        ):
            row.locked_at = now()
        if row.locked_at is not None:
            locked.add(g.id)
    return locked


def deadline(db, c):
    games = core().games_for(db, c)
    snapshots = {r.game_id: r for r in core().slate_rows(db, c)}
    times = [game_deadline(snapshots[g.id], g) for g in games]
    if not times:
        return None
    value = max(times) if c.kind == "fanwars" else min(times)
    if c.lock_at:
        value = min(value, aware(c.lock_at))
    return value


def state(db, c, r):
    x = detail(db, c)
    if c.status == "canceled":
        return "Canceled"
    if c.status in {"final", "no_contest"}:
        return "Closed — Final"
    if (
        c.status == "draft"
        or not x.enabled
        or not c.published_at
        or now() < aware(x.entry_open_at)
    ):
        return "Upcoming"
    if (r.season, r.week) != (
        core().settings.current_season_year,
        core().competition_week(core().settings.current_season_year, now()),
    ):
        return (
            "Closed — Entries ended"
            if r.season < core().settings.current_season_year
            or r.week < core().competition_week(r.season, now())
            else "Upcoming"
        )
    games = core().games_for(db, c)
    if any(not g.start_date for g in games):
        return "Closed — Schedule Verification"
    locked = locked_games(db, c, games)
    end = deadline(db, c)
    if (
        end
        and now() < end
        and (len(locked) < len(games) if c.kind == "fanwars" else not locked)
        and c.locked_at is None
    ):
        return "Open"
    if c.locked_at is None:
        c.locked_at = now()
    return (
        "Closed — Results Processing"
        if all(core().result_state(g, r, now()) in {"final", "void"} for g in games)
        else "Closed — Live"
    )


def assert_open(db, c):
    r = db.get(ChallengeRound, c.round_id)
    x = detail(db, c)
    if not visible(db, c):
        fail("CHALLENGE_DISABLED", "This competition is temporarily hidden.", 409, c)
    if state(db, c, r) != "Open":
        fail("DEADLINE_PASSED", "This competition is not open for entries.", 409, c)
    snapshots = {g.game_id: g.snapshot for g in core().slate_rows(db, c)}
    if not all(
        core().game_identity_matches(g, snapshots[g.id], r)
        for g in core().games_for(db, c)
    ):
        fail(
            "TEMPORARY_DATA_FAILURE",
            "The published schedule needs verification.",
            503,
            c,
        )


def create(db, p, actor):
    r = core().ensure_round(db, p.season, p.week)
    variant = "primary"
    if p.entry_open_at.tzinfo is None:
        fail("INVALID_CONFIGURATION", "Entry opening needs a timezone.", 422)
    if p.kind == "creator":
        profile = db.get(ChallengeCreator, p.creator_id) if p.creator_id else None
        if not profile:
            fail("INVALID_CONFIGURATION", "Select a registered creator.", 422)
        variant = f"creator-{profile.id}"
    elif p.creator_id is not None:
        fail("INVALID_CONFIGURATION", "Creator belongs to creator contests only.", 422)
    if p.kind == "survivor":
        series = db.get(ChallengeSurvivorSeries, p.series_id) if p.series_id else None
        if (
            not series
            or series.season != p.season
            or not series.start_week <= p.week <= series.end_week
        ):
            fail(
                "INVALID_CONFIGURATION",
                "Choose a series containing this season and week.",
                422,
            )
        variant = f"series-{series.id}"
    elif p.series_id is not None:
        fail("INVALID_CONFIGURATION", "Series belongs to survivor contests only.", 422)
    if (
        db.query(WeeklyChallenge)
        .filter_by(round_id=r.id, kind=p.kind, variant=variant)
        .first()
    ):
        fail("DUPLICATE_COMPETITION", "This competition already exists for the week.")
    c = WeeklyChallenge(
        round_id=r.id, kind=p.kind, variant=variant, rules_version="experiences-v1"
    )
    db.add(c)
    db.flush()
    db.add(
        ChallengeExperience(
            challenge_id=c.id,
            creator_id=p.creator_id,
            series_id=p.series_id,
            entry_open_at=p.entry_open_at,
        )
    )
    core().audit(db, c, actor, "create_experience", p.model_dump(mode="json"))
    db.commit()
    return c


def configure(db, c, p, actor):
    if c.version != p.expected_version:
        fail("VERSION_CONFLICT", "Reload the current competition version.", 409, c)
    if c.status != "draft":
        fail(
            "IMMUTABLE_RULES", "Published salaries, rules and slate are frozen.", 409, c
        )
    salary_ids = [s.player_id for s in p.salaries]
    if len(salary_ids) != len(set(salary_ids)):
        fail("INVALID_CONFIGURATION", "Each player needs one salary.", 422, c)
    if salary_ids and db.query(Player.id).filter(
        Player.id.in_(salary_ids)
    ).count() != len(salary_ids):
        fail("INVALID_CONFIGURATION", "Salary player does not exist.", 422, c)
    picks = [s.model_dump(exclude_none=True) for s in p.creator_picks]
    if len(picks) != len({s.get("game_id") for s in picks}):
        fail(
            "INVALID_CONFIGURATION",
            "Each creator game needs exactly one prediction.",
            422,
            c,
        )
    if picks and db.query(Game.id).filter(
        Game.id.in_({s.get("game_id") for s in picks})
    ).count() != len({s.get("game_id") for s in picks}):
        fail("INVALID_CONFIGURATION", "Creator game does not exist.", 422, c)
    c.config = p.model_dump(
        mode="json", exclude={"expected_version", "salaries", "creator_picks"}
    )
    db.query(ChallengeSalary).filter_by(challenge_id=c.id).delete(
        synchronize_session=False
    )
    db.query(ChallengeCreatorPick).filter_by(challenge_id=c.id).delete(
        synchronize_session=False
    )
    if c.kind != "millionaire" and p.salaries:
        fail(
            "INVALID_CONFIGURATION",
            "Salaries belong to Fantasy Millionaire only.",
            422,
            c,
        )
    if c.kind != "creator" and picks:
        fail(
            "INVALID_CONFIGURATION",
            "Creator predictions belong to creator contests only.",
            422,
            c,
        )
    for s in p.salaries:
        db.add(
            ChallengeSalary(
                challenge_id=c.id, player_id=s.player_id, salary=Decimal(str(s.salary))
            )
        )
    for s in picks:
        if set(s) != {"game_id", "team"}:
            fail(
                "INVALID_CONFIGURATION",
                "Creator predictions require a game and team.",
                422,
                c,
            )
        db.add(
            ChallengeCreatorPick(
                challenge_id=c.id, game_id=s["game_id"], team=s["team"]
            )
        )
    c.version += 1
    core().audit(db, c, actor, "configure_experience", p.model_dump(mode="json"))
    db.commit()


def validate(db, c):
    svc = core()
    r = db.get(ChallengeRound, c.round_id)
    x = detail(db, c)
    issues, games = svc.validate_slate_games(db, c, c.config)
    ids = c.config.get("game_ids", [])
    if not x.enabled:
        issues.append("Enable this competition before publishing.")
    if not games or aware(x.entry_open_at) >= min(
        (aware(g.start_date) for g in games if g.start_date), default=now()
    ):
        issues.append("Entries must open before the first kickoff.")
    if c.kind == "millionaire":
        available = {
            p["id"]: p
            for p in svc.catalog(db, r.season, r.week)["players"]
            if p["game_id"] in ids
        }
        selected = c.config.get("player_ids", [])
        pool = [available[p] for p in selected if p in available]
        prices = {
            p.player_id: float(p.salary)
            for p in db.query(ChallengeSalary).filter_by(challenge_id=c.id)
        }
        if (
            len(pool) != len(selected)
            or len(set(selected)) != len(selected)
            or set(prices) != set(selected)
        ):
            issues.append(
                "Every distinct eligible player needs one reviewed salary; no extra salary rows."
            )
        if {p["game_id"] for p in pool} != set(ids):
            issues.append("Every salary slate game must supply eligible players.")
        # Cheapest feasible six-player formation must fit the published budget.
        by_pos = {
            pos: sorted(
                (prices.get(p["id"], 101) for p in pool if p["position"] == pos)
            )
            for pos in ("QB", "RB", "WR", "TE")
        }
        if (
            not by_pos["QB"]
            or not by_pos["RB"]
            or len(by_pos["WR"]) < 2
            or not by_pos["TE"]
        ):
            issues.append("Pool must fill QB, RB, two WRs, TE and a distinct FLEX.")
        else:
            remaining = by_pos["RB"][1:] + by_pos["WR"][2:] + by_pos["TE"][1:]
            if (
                not remaining
                or by_pos["QB"][0]
                + by_pos["RB"][0]
                + sum(by_pos["WR"][:2])
                + by_pos["TE"][0]
                + min(remaining)
                > 100
            ):
                issues.append("No legal six-player lineup fits the $100 budget.")
        try:
            svc.get_scoring_rules()
        except ValueError:
            issues.append("Canonical CFFB scoring is unavailable.")
    elif c.config.get("player_ids"):
        issues.append("Only Fantasy Millionaire uses a player pool.")
    if c.kind == "creator":
        creator = db.get(ChallengeCreator, x.creator_id)
        picks = list(db.query(ChallengeCreatorPick).filter_by(challenge_id=c.id))
        game_map = {g.id: g for g in games}
        if not creator or not creator.authorized or not creator.active:
            issues.append("Creator participation must be approved and active.")
        if (
            len(ids) != 10
            or len(picks) != 10
            or {p.game_id for p in picks} != set(ids)
            or any(
                p.game_id not in game_map
                or p.team
                not in (game_map[p.game_id].home_team, game_map[p.game_id].away_team)
                for p in picks
            )
        ):
            issues.append(
                "Creator must submit one approved prediction for each of the same 10 games."
            )
    if c.kind == "fanwars":
        ids_allowed = {s["id"] for s in schools(db)}
        if not ids_allowed:
            issues.append(
                "Configure current Power Four school/conference metadata first."
            )
        if any(
            a == b or a not in ids_allowed or b not in ids_allowed
            for a, b in c.config.get("rivalries", [])
        ):
            issues.append("Rivalry schools must be distinct supported programs.")
    if c.kind == "survivor":
        series = db.get(ChallengeSurvivorSeries, x.series_id)
        if not series or not series.active:
            issues.append("An active survivor series is required.")
        elif (
            r.week == series.start_week
            and games
            and series.first_lock_at
            and any(
                g.start_date and aware(g.start_date) < aware(series.first_lock_at)
                for g in games
            )
        ):
            issues.append(
                "Series registration must close no later than its first kickoff."
            )
        elif r.week > series.start_week and aware(series.first_lock_at) > now():
            issues.append("The series first lock must precede subsequent weeks.")
    return issues, games


def publish(db, c, version, actor):
    if c.version != version:
        fail("VERSION_CONFLICT", "Reload before publishing.", 409, c)
    if c.status != "draft":
        fail("IMMUTABLE_RULES", "Competition is already published.", 409, c)
    issues, games = validate(db, c)
    if issues:
        fail("INVALID_CONFIGURATION", " ".join(issues), 422, c)
    r = db.get(ChallengeRound, c.round_id)
    if (r.season, r.week) < (
        core().settings.current_season_year,
        core().competition_week(core().settings.current_season_year, now()),
    ):
        fail("CHALLENGE_CLOSED", "Cannot publish a past week.", 409, c)
    config = dict(c.config)
    x = detail(db, c)
    if c.kind == "creator":
        config["creator_snapshot"] = creator_read(
            db.get(ChallengeCreator, x.creator_id)
        )
    if c.kind == "fanwars":
        config["school_snapshot"] = schools(db)
    if c.kind == "millionaire":
        config.update(
            scoring_rules=core().get_scoring_rules(),
            scoring_version=core().CALCULATION_VERSION,
            projection_snapshot=published_projections(
                db, c, config.get("player_ids", [])
            ),
        )
    core().freeze_slate(db, c, games, config.get("player_ids", []))
    c.config = config
    c.status = "published"
    c.published_at = now()
    c.version += 1
    c.lock_at = (max if c.kind == "fanwars" else min)(
        aware(g.start_date) for g in games
    )
    if c.kind == "survivor":
        series = db.get(ChallengeSurvivorSeries, detail(db, c).series_id)
        if r.week == series.start_week:
            c.lock_at = min(aware(c.lock_at), aware(series.first_lock_at))
    core().audit(
        db,
        c,
        actor,
        "publish_experience",
        {
            "version": c.version,
            "config": config,
            "lock_at": c.lock_at,
            "rules_version": c.rules_version,
        },
    )
    db.commit()


def allegiance(db, c, user, school_id):
    assert_open(db, c)
    if c.kind != "fanwars":
        fail("INVALID_ENTRY", "School allegiance belongs to Fan Wars.", 422, c)
    # User row serializes allegiance choices across distinct Fan Wars contests.
    db.query(User).filter_by(id=user.id).with_for_update().one()
    r = db.get(ChallengeRound, c.round_id)
    previous = (
        db.query(ChallengeFanMembership)
        .filter_by(user_id=user.id, season=r.season, week=r.week)
        .one_or_none()
    )
    if previous:
        if previous.school_id != school_id:
            fail(
                "ALLEGIANCE_LOCKED",
                "Your school is fixed for this week. Choose a different school next week.",
                409,
                c,
            )
        return previous
    school = next(
        (
            s
            for s in c.config.get("school_snapshot", schools(db))
            if s["id"] == school_id
        ),
        None,
    )
    if not school:
        fail("INVALID_ENTRY", "Select a supported Power Four school.", 422, c)
    row = ChallengeFanMembership(
        user_id=user.id,
        season=r.season,
        week=r.week,
        school_id=school_id,
        school_name=school["name"],
        conference=school["conference"],
    )
    db.add(row)
    core().audit(db, c, user.id, "choose_school", school)
    db.commit()
    return row


def _series_state(db, x, user_id, before_week=None):
    enrollment = (
        db.query(ChallengeSurvivorEnrollment)
        .filter_by(series_id=x.series_id, user_id=user_id)
        .one_or_none()
    )
    picks = (
        list(
            db.query(ChallengeSurvivorPick)
            .filter_by(enrollment_id=enrollment.id)
            .order_by(ChallengeSurvivorPick.week)
        )
        if enrollment
        else []
    )
    relevant = [p for p in picks if before_week is None or p.week < before_week]
    status = (
        "not_joined"
        if enrollment is None
        else "eliminated"
        if any(p.outcome in {"eliminated", "ineligible"} for p in relevant)
        else "processing"
        if any(p.outcome == "pending" for p in relevant)
        else "active"
    )
    return enrollment, picks, status


def ineligible_pool_ids(db, c):
    """Recheck the existing canonical eligibility policy without changing frozen salaries/history."""
    r = db.get(ChallengeRound, c.round_id)
    current = {
        p["id"]: p["game_id"] for p in core().catalog(db, r.season, r.week)["players"]
    }
    return {
        p.player_id
        for p in db.query(ChallengePoolPlayer).filter_by(challenge_id=c.id)
        if current.get(p.player_id) != p.game_id
    }


def validate_entry(db, c, p, complete, user_id):
    selections = [s.model_dump(exclude_none=True) for s in p.selections]
    r = db.get(ChallengeRound, c.round_id)
    x = detail(db, c)
    if p.tiebreaker is not None:
        fail("INVALID_ENTRY", "This mode has no score tiebreaker.", 422, c)
    if c.kind == "millionaire":
        pool = {
            p.player_id: p
            for p in db.query(ChallengePoolPlayer).filter_by(challenge_id=c.id)
        }
        prices = {
            p.player_id: p.salary
            for p in db.query(ChallengeSalary).filter_by(challenge_id=c.id)
        }
        ids = [s.get("player_id") for s in selections]
        slots = [s.get("slot") for s in selections]
        if len(ids) > 6 or len(set(ids)) != len(ids) or len(set(slots)) != len(slots):
            fail("INVALID_ENTRY", "Choose six distinct players and slots.", 422, c)
        if any(
            set(s) != {"player_id", "slot"}
            or s["player_id"] not in pool
            or s["player_id"] not in prices
            or s["slot"] not in SLOTS
            or pool[s["player_id"]].snapshot["position"]
            not in (
                {"RB", "WR", "TE"}
                if s["slot"] == "FLEX"
                else {"WR"}
                if s["slot"] in {"WR1", "WR2"}
                else {s["slot"]}
            )
            for s in selections
        ):
            fail(
                "INVALID_ENTRY",
                "Choose eligible published players in their required slots.",
                422,
                c,
            )
        if set(ids) & ineligible_pool_ids(db, c):
            fail(
                "PLAYER_INELIGIBLE",
                "A selected player is no longer eligible for this slate. Choose another player.",
                422,
                c,
            )
        if sum((prices[pid] for pid in ids), Decimal(0)) > 100:
            fail(
                "BUDGET_EXCEEDED",
                "The six-player lineup cannot exceed $100 virtual credits.",
                422,
                c,
            )
        if complete and set(slots) != set(SLOTS):
            fail("INCOMPLETE_ENTRY", "Fill QB, RB, WR, WR, TE and FLEX.", 422, c)
    else:
        games = {row.game_id: row.snapshot for row in core().slate_rows(db, c)}
        ids = [s.get("game_id") for s in selections]
        if len(set(ids)) != len(ids) or any(
            set(s) != {"game_id", "team"}
            or s["game_id"] not in games
            or s["team"]
            not in (games[s["game_id"]]["home_team"], games[s["game_id"]]["away_team"])
            for s in selections
        ):
            fail("INVALID_ENTRY", "Choose one published team per game.", 422, c)
        maximum = (
            10 if c.kind == "creator" else 1 if c.kind == "survivor" else len(games)
        )
        if len(selections) > maximum or (
            complete
            and (len(selections) != maximum if c.kind != "fanwars" else not selections)
        ):
            fail(
                "INCOMPLETE_ENTRY",
                f"Choose {maximum} picks."
                if c.kind != "fanwars"
                else "Choose at least one eligible game.",
                422,
                c,
            )
        if c.kind == "fanwars":
            member = (
                db.query(ChallengeFanMembership)
                .filter_by(user_id=user_id, season=r.season, week=r.week)
                .one_or_none()
            )
            if not member:
                fail(
                    "SCHOOL_REQUIRED",
                    "Choose the school you represent before saving picks.",
                    422,
                    c,
                )
            old = core().entry_for(db, c, user_id)
            old_picks = {s["game_id"]: s["team"] for s in old.selections} if old else {}
            new_picks = {s["game_id"]: s["team"] for s in selections}
            if any(
                old_picks.get(gid) != new_picks.get(gid) for gid in locked_games(db, c)
            ):
                fail(
                    "PICK_LOCKED",
                    "A started game cannot be added, changed or removed.",
                    409,
                    c,
                )
        if c.kind == "survivor":
            series = (
                db.query(ChallengeSurvivorSeries)
                .filter_by(id=x.series_id)
                .with_for_update()
                .one()
            )
            enrollment, prior, status = _series_state(db, x, user_id, r.week)
            if not series.active or status in {"eliminated", "processing"}:
                fail(
                    "SURVIVOR_INELIGIBLE",
                    "You are eliminated or waiting for a prior result.",
                    409,
                    c,
                )
            if enrollment is None and (
                r.week != series.start_week
                or now() >= aware(series.first_lock_at)
                or now() < aware(series.entry_open_at)
            ):
                fail(
                    "SERIES_ENTRY_CLOSED",
                    "This series has started. Join the next series.",
                    409,
                    c,
                )
            if r.week > series.start_week and {
                v.week for v in prior if v.outcome in {"survived", "void_advanced"}
            } != set(range(series.start_week, r.week)):
                fail(
                    "SURVIVOR_INELIGIBLE",
                    "Every previous week must be officially resolved and survived.",
                    409,
                    c,
                )
            used = {v.school_key for v in prior if v.week != r.week}
            if any(school_key(s["team"]) in used for s in selections):
                fail(
                    "TEAM_ALREADY_USED",
                    "You already used this team in the survivor series.",
                    422,
                    c,
                )
    return selections


def persist_observed_locks(db, c):
    # Preserve only observed kickoff locks after rolling back a rejected entry.
    # This cannot commit partially edited selections or an enrollment.
    cid = c.id
    closed = c.locked_at
    observed = {
        row.game_id: row.locked_at
        for row in core().slate_rows(db, c)
        if row.locked_at is not None
    }
    db.rollback()
    fresh = core().challenge_or_404(db, cid, lock=True)
    for row in core().slate_rows(db, fresh):
        if row.game_id in observed and row.locked_at is None:
            row.locked_at = observed[row.game_id]
    if closed and fresh.locked_at is None:
        fresh.locked_at = closed
    db.commit()


def save_entry(db, c, user, p):
    try:
        return _save_entry(db, c, user, p)
    except HTTPException:
        persist_observed_locks(db, c)
        raise


def _save_entry(db, c, user, p):
    assert_open(db, c)
    # Explicit server actor is never accepted from the request payload.
    selections = validate_entry(db, c, p, p.submit, user.id)
    e = core().entry_for(db, c, user.id)
    if (e.revision if e else 0) != p.expected_revision:
        fail("VERSION_CONFLICT", "Reload your saved entry before changing it.", 409, c)
    if e and e.status == "submitted" and not p.submit:
        fail("INVALID_ENTRY", "Submit an update to edit an official entry.", 422, c)
    if e is None:
        e = ChallengeEntry(challenge_id=c.id, user_id=user.id)
        db.add(e)
        db.flush()
    e.selections = selections
    e.tiebreaker = None
    e.revision = (e.revision or 0) + 1
    e.status = "submitted" if p.submit else "draft"
    e.submitted_at = now() if p.submit else None
    r = db.get(ChallengeRound, c.round_id)
    x = detail(db, c)
    if c.kind == "fanwars" and db.get(ChallengeEntrySchool, e.id) is None:
        member = (
            db.query(ChallengeFanMembership)
            .filter_by(user_id=user.id, season=r.season, week=r.week)
            .one()
        )
        db.add(ChallengeEntrySchool(entry_id=e.id, membership_id=member.id))
    if c.kind == "survivor" and p.submit:
        enrollment = (
            db.query(ChallengeSurvivorEnrollment)
            .filter_by(series_id=x.series_id, user_id=user.id)
            .one_or_none()
        )
        if enrollment is None:
            enrollment = ChallengeSurvivorEnrollment(
                series_id=x.series_id, user_id=user.id
            )
            db.add(enrollment)
            db.flush()
        pick = db.get(ChallengeSurvivorPick, e.id)
        if pick is None:
            pick = ChallengeSurvivorPick(
                entry_id=e.id, enrollment_id=enrollment.id, week=r.week
            )
            db.add(pick)
        pick.school_key = school_key(selections[0]["team"])
        pick.outcome = "pending"
    assert_open(db, c)
    db.commit()
    db.refresh(e)
    return e


def _won(g, team):
    return (team == g.home_team and g.home_points > g.away_points) or (
        team == g.away_team and g.away_points > g.home_points
    )


def settle(db, c, *, actor=None, reason="Scheduled settlement", force=False):
    svc = core()
    x = detail(db, c)
    r = db.get(ChallengeRound, c.round_id)
    if c.status == "draft":
        return "upcoming"
    if not x.enabled and not force:
        c.last_scored_at = now()
        db.commit()
        return c.status
    games = svc.games_for(db, c)
    game_map = {g.id: g for g in games}
    snapshots = {row.game_id: row.snapshot for row in svc.slate_rows(db, c)}
    locked = locked_games(db, c, games)
    end = deadline(db, c)
    if (
        c.kind != "fanwars"
        and not locked
        and end
        and now() < end
        and c.status != "canceled"
    ):
        c.last_scored_at = now()
        db.commit()
        return "open"
    if end and now() >= end and c.locked_at is None:
        c.locked_at = now()
    states = {g.id: svc.result_state(g, r, now()) for g in games}
    identity = all(svc.game_identity_matches(g, snapshots[g.id], r) for g in games)
    entries = list(
        db.query(ChallengeEntry)
        .filter_by(challenge_id=c.id, status="submitted")
        .order_by(ChallengeEntry.id)
    )
    creator_picks = list(db.query(ChallengeCreatorPick).filter_by(challenge_id=c.id))
    decisions = {
        d.game_id
        for d in db.query(ChallengeGameDecision).filter_by(
            challenge_id=c.id, active=True
        )
    }
    for gid in decisions:
        if gid in states:
            states[gid] = "void"
    chosen = {s["player_id"] for e in entries for s in e.selections if "player_id" in s}
    stats = {
        (s.player_id, s.game_id): s
        for s in db.query(PlayerGameStat).filter(
            PlayerGameStat.player_id.in_(chosen),
            PlayerGameStat.game_id.in_(game_map),
            PlayerGameStat.season == r.season,
            PlayerGameStat.source == "espn_final_boxscore",
        )
    }
    pool = {
        p.player_id: p
        for p in db.query(ChallengePoolPlayer).filter_by(challenge_id=c.id)
    }
    nonparticipants = (
        svc.confirmed_nonparticipant_ids(
            db, season=r.season, week=r.week, player_ids=chosen
        )
        if c.kind == "millionaire"
        else set()
    )
    missing_enrollments = []
    if c.kind == "survivor" and (c.status == "canceled" or end and now() >= end):
        for enrollment in db.query(ChallengeSurvivorEnrollment).filter_by(
            series_id=x.series_id
        ):
            if (
                not db.query(ChallengeSurvivorPick)
                .filter_by(enrollment_id=enrollment.id, week=r.week)
                .first()
            ):
                missing_enrollments.append(enrollment.id)
    history = (
        [
            (p.enrollment_id, p.week, p.outcome, p.school_key)
            for p in db.query(ChallengeSurvivorPick)
            .join(ChallengeSurvivorEnrollment)
            .filter(
                ChallengeSurvivorEnrollment.series_id == x.series_id,
                ChallengeSurvivorPick.week < r.week,
            )
            .order_by(ChallengeSurvivorPick.enrollment_id, ChallengeSurvivorPick.week)
        ]
        if c.kind == "survivor"
        else []
    )
    enrollments = (
        [
            e.id
            for e in db.query(ChallengeSurvivorEnrollment)
            .filter_by(series_id=x.series_id)
            .order_by(ChallengeSurvivorEnrollment.id)
        ]
        if c.kind == "survivor"
        else []
    )
    source = {
        "config": c.config,
        "games": [
            (
                g.id,
                g.schedule_status,
                g.start_date,
                g.home_team,
                g.away_team,
                g.home_points,
                g.away_points,
                states[g.id],
            )
            for g in games
        ],
        "entries": [(e.id, e.revision, e.selections) for e in entries],
        "creator": [(p.game_id, p.team) for p in creator_picks],
        "stats": [
            (s.player_id, s.game_id, s.stats)
            for s in sorted(stats.values(), key=lambda s: s.id)
        ],
        "nonparticipants": sorted(nonparticipants),
        "decisions": sorted(decisions),
        "identity": identity,
        "canceled": c.status == "canceled",
        "survivor_history": history,
        "enrollments": enrollments,
        "end_reached": bool(end and now() >= end),
    }
    fingerprint = hashlib.sha256(
        json.dumps(source, sort_keys=True, default=str).encode()
    ).hexdigest()
    c.last_scored_at = now()
    # Earlier survivor outcomes are fingerprinted, so corrections reconcile descendants without duplicate settlements.
    if c.source_hash == fingerprint and not force:
        db.commit()
        return c.status
    globally_resolved = (
        bool(games)
        and all(v in {"final", "void"} for v in states.values())
        and identity
    )
    void_all = bool(games) and all(v == "void" for v in states.values())
    no_contest = (void_all and c.kind != "survivor") or c.status == "canceled"
    creator_correct = (
        sum(
            states.get(p.game_id) == "final" and _won(game_map[p.game_id], p.team)
            for p in creator_picks
        )
        if c.kind == "creator"
        else None
    )
    scores = []
    for e in entries:
        points = Decimal(0)
        correct = eligible = 0
        missing = False
        observed = False
        outcome = None
        player_points = {}
        for pick in e.selections:
            if c.kind == "millionaire":
                p = pool.get(pick["player_id"])
                g = game_map.get(p.game_id) if p else None
                if not g:
                    missing = True
                    continue
                if states[g.id] == "void":
                    observed = True
                    player_points[p.player_id] = 0.0
                    continue
                fact = stats.get((p.player_id, g.id))
                value = (
                    svc.points_from_verified_stats(
                        fact.stats,
                        position=p.snapshot["position"],
                        rules=c.config["scoring_rules"],
                    )
                    if fact
                    and fact.week == g.week
                    and c.config.get("scoring_version") == svc.CALCULATION_VERSION
                    else None
                )
                if (
                    value is None
                    and p.player_id in nonparticipants
                    and states[g.id] == "final"
                ):
                    value = 0.0
                if value is None:
                    missing = True
                else:
                    points += Decimal(str(value))
                    player_points[p.player_id] = float(value)
                    observed = True
            else:
                g = game_map[pick["game_id"]]
                if c.kind == "survivor":
                    if states[g.id] == "final" and g.home_points != g.away_points:
                        outcome = "survived" if _won(g, pick["team"]) else "eliminated"
                        observed = True
                    elif g.id in decisions:
                        outcome = "void_advanced"
                        observed = True
                    else:
                        missing = True
                        outcome = "pending"
                if states[g.id] == "final" and g.home_points != g.away_points:
                    eligible += 1
                    observed = True
                    if _won(g, pick["team"]):
                        correct += 1
                        points += Decimal(c.config.get("correct_points", 10))
        resolved = globally_resolved and not missing
        if c.kind == "survivor":
            sp = db.get(ChallengeSurvivorPick, e.id)
            if sp:
                enrollment = db.get(ChallengeSurvivorEnrollment, sp.enrollment_id)
                prior = list(
                    db.query(ChallengeSurvivorPick)
                    .filter(
                        ChallengeSurvivorPick.enrollment_id == sp.enrollment_id,
                        ChallengeSurvivorPick.week < r.week,
                    )
                    .order_by(ChallengeSurvivorPick.week)
                )
                series = db.get(ChallengeSurvivorSeries, x.series_id)
                if any(p.outcome == "eliminated" for p in prior) or {
                    p.week for p in prior
                } != set(range(series.start_week, r.week)):
                    outcome = "ineligible"
                    resolved = True
                elif any(p.outcome in {"pending", "ineligible"} for p in prior):
                    outcome = "pending"
                    resolved = False
                if c.status == "canceled":
                    outcome = "void_advanced"
                    resolved = True
                sp.outcome = outcome or "pending"
                points = Decimal(
                    sum(p.outcome in {"survived", "void_advanced"} for p in prior)
                    + (outcome in {"survived", "void_advanced"})
                )
                # Missed prior weeks are permanent eliminations after their published lock.
                for week in range(series.start_week, r.week):
                    if week not in {p.week for p in prior}:
                        outcome = "ineligible"
                        sp.outcome = "ineligible"
                        resolved = True
        score = db.query(ChallengeScore).filter_by(
            entry_id=e.id
        ).one_or_none() or ChallengeScore(entry_id=e.id)
        score.raw_points = (
            points
            if identity and (observed or c.kind == "survivor") and not no_contest
            else None
        )
        score.status = (
            "no_contest" if no_contest else "final" if resolved else "processing"
        )
        score.source_hash = fingerprint
        score.tiebreaker_error = None
        score.details = {
            "correct": correct,
            "eligible": eligible,
            "game_states": states,
            "outcome": outcome,
            "identity_verified": identity,
            "creator_correct": creator_correct,
            "creator_score": creator_correct * c.config.get("correct_points", 10)
            if creator_correct is not None
            else None,
            "pending_stats": missing,
            "player_points": player_points,
        }
        db.add(score)
        scores.append((e, score))
    # A missed survivor pick is represented as a missed event, never a fabricated user prediction.
    if c.kind == "survivor" and missing_enrollments:
        for enrollment_id in missing_enrollments:
            enrollment = db.get(ChallengeSurvivorEnrollment, enrollment_id)
            existing = svc.entry_for(db, c, enrollment.user_id)
            if existing is None:
                existing = ChallengeEntry(
                    challenge_id=c.id,
                    user_id=enrollment.user_id,
                    status="void" if c.status == "canceled" else "missed",
                    revision=0,
                    selections=[],
                )
                db.add(existing)
                db.flush()
            elif existing.status != "submitted":
                existing.status = "void" if c.status == "canceled" else "missed"
            if db.get(ChallengeSurvivorPick, existing.id) is None:
                db.add(
                    ChallengeSurvivorPick(
                        entry_id=existing.id,
                        enrollment_id=enrollment_id,
                        week=r.week,
                        school_key=f"void:{r.week}"
                        if c.status == "canceled"
                        else f"missed:{r.week}",
                        outcome="void_advanced"
                        if c.status == "canceled"
                        else "eliminated",
                    )
                )
                svc.audit(
                    db,
                    c,
                    actor,
                    "canceled_survivor_week"
                    if c.status == "canceled"
                    else "missed_survivor_pick",
                    {"user_id": enrollment.user_id, "week": r.week},
                )
    ordered = sorted(
        scores, key=lambda pair: (-(pair[1].raw_points or 0), pair[0].user_id)
    )
    previous = object()
    rank = 0
    for i, (e, score) in enumerate(ordered, 1):
        if score.raw_points != previous:
            rank = i
        score.rank = (
            rank
            if score.raw_points is not None and score.status != "no_contest"
            else None
        )
        previous = score.raw_points
    complete = (
        no_contest or globally_resolved and all(s.status == "final" for _, s in scores)
    )
    if c.kind == "survivor":
        complete = (
            all(
                p.outcome != "pending"
                for p in db.query(ChallengeSurvivorPick)
                .join(
                    ChallengeEntry, ChallengeEntry.id == ChallengeSurvivorPick.entry_id
                )
                .filter(ChallengeEntry.challenge_id == c.id)
            )
            and globally_resolved
        )
    if c.status != "canceled":
        c.status = "no_contest" if no_contest else "final" if complete else "processing"
    c.finalized_at = now() if complete else None
    c.source_hash = fingerprint
    svc.audit(
        db,
        c,
        actor,
        "correction"
        if db.query(ChallengeAudit.id)
        .filter_by(challenge_id=c.id, action="score")
        .first()
        else "score",
        {
            "reason": reason,
            "source_hash": fingerprint,
            "state": c.status,
            "source": source,
        },
    )
    db.flush()
    queue_results(db, c, scores)
    db.commit()
    return c.status


def school_standings(db, c, *, season=False, metric="accuracy", conference=None):
    from fractions import Fraction

    r = db.get(ChallengeRound, c.round_id)
    correct = ChallengeScore.details["correct"].as_integer()
    eligible = ChallengeScore.details["eligible"].as_integer()
    verified = ChallengeScore.details["identity_verified"].as_boolean()
    query = (
        db.query(
            ChallengeFanMembership.school_id,
            func.min(ChallengeFanMembership.school_name),
            func.min(ChallengeFanMembership.conference),
            func.sum(correct),
            func.sum(eligible),
            func.sum(ChallengeScore.raw_points),
            func.count(func.distinct(ChallengeFanMembership.user_id)),
        )
        .join(
            ChallengeEntrySchool,
            ChallengeEntrySchool.membership_id == ChallengeFanMembership.id,
        )
        .join(ChallengeEntry, ChallengeEntry.id == ChallengeEntrySchool.entry_id)
        .join(WeeklyChallenge, WeeklyChallenge.id == ChallengeEntry.challenge_id)
        .join(ChallengeScore, ChallengeScore.entry_id == ChallengeEntry.id)
        .join(ChallengeRound, ChallengeRound.id == WeeklyChallenge.round_id)
        .join(User, User.id == ChallengeEntry.user_id)
        .filter(
            WeeklyChallenge.kind == "fanwars",
            WeeklyChallenge.status != "canceled",
            ChallengeRound.season == r.season,
            ChallengeEntry.status == "submitted",
            User.is_active.is_(True),
            ChallengeScore.status != "no_contest",
            verified.is_(True),
            eligible > 0,
        )
    )
    if not season:
        query = query.filter(ChallengeRound.id == r.id)
    snapshot = {s["id"]: s for s in c.config.get("school_snapshot", [])}
    minimum = c.config.get("minimum_fans", 3)
    rows = []
    for school_id, name, conf, right, count, points, fans in query.group_by(
        ChallengeFanMembership.school_id
    ):
        display = snapshot.get(school_id, {"name": name, "conference": conf})
        if conference and display["conference"] != conference:
            continue
        ratio = Fraction(int(right or 0), int(count))
        rows.append(
            {
                "school_id": school_id,
                "school": display["name"],
                "conference": display["conference"],
                "correct_picks": int(right or 0),
                "eligible_picks": int(count),
                "fan_points": float(points or 0),
                "accuracy": round(float(ratio) * 100, 2),
                "active_fans": int(fans),
                "provisional": fans < minimum,
                "rank": None,
                "_metric": ratio if metric == "accuracy" else points or 0,
            }
        )
    rows.sort(
        key=lambda row: (
            row["provisional"] if metric == "accuracy" else False,
            -row["_metric"],
            row["school"],
        )
    )
    previous = None
    rank = 0
    for i, row in enumerate(rows, 1):
        key = row.pop("_metric")
        if metric == "accuracy" and row["provisional"]:
            continue
        if key != previous:
            rank = i
        row["rank"] = rank
        previous = key
    return rows


def read(db, c, user, *, admin=False, include_details=True):
    x = detail(db, c)
    r = db.get(ChallengeRound, c.round_id)
    public = admin or c.published_at is not None
    result = {
        "season": r.season,
        "week": r.week,
        "locked_game_ids": sorted(locked_games(db, c)) if public else [],
        "kind": c.kind,
        "enabled": x.enabled,
        "entry_open_at": x.entry_open_at,
        "projections": config_projection(c) if public else {},
        "participants": db.query(ChallengeEntry)
        .filter_by(challenge_id=c.id, status="submitted")
        .count(),
        "correct_points": c.config.get("correct_points", 10),
        "minimum_fans": c.config.get("minimum_fans", 3),
    }
    if (
        c.kind == "millionaire"
        and public
        and include_details
        and state(db, c, r) == "Open"
    ):
        result["ineligible_player_ids"] = sorted(ineligible_pool_ids(db, c))
    mine = core().entry_for(db, c, user.id)
    score = (
        db.query(ChallengeScore).filter_by(entry_id=mine.id).one_or_none()
        if mine
        else None
    )
    if score:
        result.update(
            your_points=float(score.raw_points)
            if score.raw_points is not None
            else None,
            your_rank=score.rank,
            personal_correct=score.details.get("correct"),
            player_points=score.details.get("player_points", {}),
        )
        if (
            c.kind == "millionaire"
            and score.status == "final"
            and result["player_points"]
        ):
            best = max(
                result["player_points"], key=lambda key: result["player_points"][key]
            )
            snapshot = (
                db.query(ChallengePoolPlayer)
                .filter_by(challenge_id=c.id, player_id=int(best))
                .one_or_none()
            )
            result["best_performer"] = snapshot.snapshot["name"] if snapshot else None
    if c.kind == "millionaire" and public and include_details:
        result["salaries"] = [
            {"player_id": s.player_id, "salary": float(s.salary)}
            for s in db.query(ChallengeSalary)
            .filter_by(challenge_id=c.id)
            .order_by(ChallengeSalary.player_id)
        ]
    if c.kind == "creator":
        creator = db.get(ChallengeCreator, x.creator_id)
        if creator and (
            admin
            or creator.authorized
            and creator.active
            or c.status in {"final", "no_contest", "canceled"}
            and c.config.get("creator_snapshot")
        ):
            result["creator"] = (
                creator_read(creator)
                if admin
                else c.config.get("creator_snapshot", creator_read(creator))
            )
        closed = deadline(db, c) is not None and now() >= deadline(db, c)
        if public and (closed or admin):
            result["creator_picks"] = [
                {"game_id": p.game_id, "team": p.team}
                for p in db.query(ChallengeCreatorPick).filter_by(challenge_id=c.id)
            ]
            games = {g.id: g for g in core().games_for(db, c)}
            identity_verified = all(
                row.game_id in games
                and core().game_identity_matches(games[row.game_id], row.snapshot, r)
                for row in core().slate_rows(db, c)
            )
            correct = (
                sum(
                    core().result_state(games[p["game_id"]], r, now()) == "final"
                    and _won(games[p["game_id"]], p["team"])
                    for p in result["creator_picks"]
                    if p["game_id"] in games
                )
                if c.published_at and identity_verified
                else None
            )
            result.update(
                creator_correct=correct,
                creator_score=correct * c.config.get("correct_points", 10)
                if correct is not None
                else None,
            )
            if (
                score
                and score.status == "final"
                and score.raw_points is not None
                and correct is not None
            ):
                result["comparison"] = (
                    "BEAT THE CREATOR"
                    if score.raw_points > result["creator_score"]
                    else "TIED THE CREATOR"
                    if score.raw_points == result["creator_score"]
                    else "CREATOR WON"
                )
    if c.kind == "fanwars" and include_details:
        member = (
            db.query(ChallengeFanMembership)
            .filter_by(user_id=user.id, season=r.season, week=r.week)
            .one_or_none()
        )
        standings = school_standings(db, c)
        season_rows = school_standings(db, c, season=True)
        result.update(
            schools=c.config.get("school_snapshot", schools(db))
            if include_details
            else [],
            school_standings=standings if include_details else [],
            allegiance={
                "id": member.school_id,
                "name": member.school_name,
                "conference": member.conference,
            }
            if member
            else None,
            personal_contribution=float(score.raw_points)
            if score and score.raw_points is not None
            else None,
            personal_correct=score.details.get("correct") if score else None,
            school_week_rank=next(
                (
                    s["rank"]
                    for s in standings
                    if member and s["school_id"] == member.school_id
                ),
                None,
            ),
            school_season_rank=next(
                (
                    s["rank"]
                    for s in season_rows
                    if member and s["school_id"] == member.school_id
                ),
                None,
            ),
        )
        by_school = {s["school_id"]: s for s in standings}
        names = {
            s["id"]: s["name"] for s in c.config.get("school_snapshot", schools(db))
        }
        result["rivalries"] = [
            {
                "a": {
                    "school_id": a,
                    "school": names.get(a),
                    "fan_points": by_school.get(a, {}).get("fan_points", 0),
                    "active_fans": by_school.get(a, {}).get("active_fans", 0),
                },
                "b": {
                    "school_id": b,
                    "school": names.get(b),
                    "fan_points": by_school.get(b, {}).get("fan_points", 0),
                    "active_fans": by_school.get(b, {}).get("active_fans", 0),
                },
                "winner": None
                if c.status != "final" or not (by_school.get(a, {}).get("active_fans", 0) + by_school.get(b, {}).get("active_fans", 0))
                else "tie"
                if by_school.get(a, {}).get("fan_points", 0)
                == by_school.get(b, {}).get("fan_points", 0)
                else names[a]
                if by_school.get(a, {}).get("fan_points", 0)
                > by_school.get(b, {}).get("fan_points", 0)
                else names[b],
            }
            for a, b in c.config.get("rivalries", [])
        ]
    if c.kind == "survivor":
        series = db.get(ChallengeSurvivorSeries, x.series_id)
        enrollment, picks, status = _series_state(db, x, user.id, r.week + 1)
        picks = [p for p in picks if p.week <= r.week]
        all_enrollments = list(
            db.query(ChallengeSurvivorEnrollment).filter_by(series_id=x.series_id)
        )
        eliminated = set()
        all_picks = list(
            db.query(ChallengeSurvivorPick)
            .join(ChallengeSurvivorEnrollment)
            .filter(
                ChallengeSurvivorEnrollment.series_id == x.series_id,
                ChallengeSurvivorPick.week <= r.week,
            )
        )
        for p in all_picks:
            if p.outcome in {"eliminated", "ineligible"}:
                eliminated.add(p.enrollment_id)
        survived = sum(p.outcome in {"survived", "void_advanced"} for p in picks)
        if status == "active" and survived == series.end_week - series.start_week + 1:
            status = (
                "joint_winner"
                if len(all_enrollments) - len(eliminated) > 1
                else "winner"
            )
        result.update(
            series=series_read(series),
            survivor_status=status,
            weeks_survived=survived,
            remaining_survivors=len(all_enrollments) - len(eliminated),
            eliminated=len(eliminated),
        )
        for p in picks:
            e = db.get(ChallengeEntry, p.entry_id)
            pick = e.selections[0] if e.selections else {}
            g = db.get(Game, pick.get("game_id")) if pick else None
            result.setdefault("previous_picks", []).append(
                {
                    "week": p.week,
                    "team": pick.get("team"),
                    "opponent": (
                        g.away_team if pick.get("team") == g.home_team else g.home_team
                    )
                    if g
                    else None,
                    "outcome": p.outcome,
                    "game": core().game_read(g) if g else None,
                }
            )
    result["corrections"] = [
        a.details["reason"]
        for a in db.query(ChallengeAudit)
        .filter(
            ChallengeAudit.challenge_id == c.id,
            ChallengeAudit.actor_id.is_not(None),
            ChallengeAudit.action.in_(
                ["creator_correction", "void_advance", "correction"]
            ),
        )
        .order_by(ChallengeAudit.id.desc())
        .limit(5)
        if a.details.get("reason")
    ]
    return ExperienceRead.model_validate(result).model_dump()


def leaderboard(db, c, user, *, metric="accuracy", conference=None, season=False):
    if c.status == "draft" or not visible(db, c):
        fail("NOT_PUBLISHED", "This competition has not opened.", 409, c)
    x = detail(db, c)
    closed = deadline(db, c) is not None and now() >= deadline(db, c)
    if c.kind == "survivor":
        round_ = db.get(ChallengeRound, c.round_id)
        series = db.get(ChallengeSurvivorSeries, x.series_id)
        aggregates = (
            select(
                ChallengeSurvivorEnrollment.user_id.label("uid"),
                func.sum(
                    case(
                        (
                            ChallengeSurvivorPick.outcome.in_(
                                ["survived", "void_advanced"]
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("points"),
                func.max(
                    case(
                        (
                            ChallengeSurvivorPick.outcome.in_(
                                ["eliminated", "ineligible"]
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("lost"),
                func.max(
                    case((ChallengeSurvivorPick.outcome == "pending", 1), else_=0)
                ).label("pending"),
            )
            .outerjoin(
                ChallengeSurvivorPick,
                and_(
                    ChallengeSurvivorPick.enrollment_id
                    == ChallengeSurvivorEnrollment.id,
                    ChallengeSurvivorPick.week <= round_.week,
                ),
            )
            .join(User, User.id == ChallengeSurvivorEnrollment.user_id)
            .where(
                ChallengeSurvivorEnrollment.series_id == x.series_id,
                User.is_active.is_(True),
            )
            .group_by(ChallengeSurvivorEnrollment.user_id)
            .subquery()
        )
        ranked = select(
            aggregates,
            func.rank().over(order_by=aggregates.c.points.desc()).label("rank"),
        ).subquery()
        q = db.query(
            User, ranked.c.points, ranked.c.rank, ranked.c.lost, ranked.c.pending
        ).join(ranked, ranked.c.uid == User.id)

        def row_read(row):
            u, points, rank, lost, pending = row
            return {
                **core().participant(u),
                "points": float(points or 0),
                "rank": int(rank),
                "status": "eliminated"
                if lost
                else "processing"
                if pending
                else "active",
                "correct_picks": None,
                "selections": None,
            }
    else:
        aggregates = (
            select(
                ChallengeEntry.id.label("eid"),
                ChallengeEntry.user_id.label("uid"),
                ChallengeScore.raw_points.label("points"),
            )
            .outerjoin(ChallengeScore, ChallengeScore.entry_id == ChallengeEntry.id)
            .join(User, User.id == ChallengeEntry.user_id)
            .where(
                ChallengeEntry.challenge_id == c.id,
                ChallengeEntry.status == "submitted",
                User.is_active.is_(True),
            )
            .subquery()
        )
        ranked = select(
            aggregates,
            func.rank()
            .over(order_by=aggregates.c.points.desc().nullslast())
            .label("rank"),
        ).subquery()
        q = (
            db.query(User, ChallengeEntry, ChallengeScore, ranked.c.rank)
            .join(ranked, ranked.c.uid == User.id)
            .join(ChallengeEntry, ChallengeEntry.id == ranked.c.eid)
            .outerjoin(ChallengeScore, ChallengeScore.entry_id == ChallengeEntry.id)
        )

        def row_read(row):
            u, e, s, rank = row
            return {
                **core().participant(u),
                "points": float(s.raw_points)
                if s and s.raw_points is not None
                else None,
                "rank": int(rank),
                "status": s.status if s else "pending",
                "correct_picks": s.details.get("correct") if s else None,
                "selections": e.selections if closed or u.id == user.id else None,
            }

    total = q.count()
    rows = [row_read(row) for row in q.order_by(ranked.c.rank, User.id).limit(10)]
    mine = q.filter(User.id == user.id).first()
    return {
        "challenge_id": c.id,
        "kind": c.kind,
        "unit": "weeks survived"
        if c.kind == "survivor"
        else "fantasy points"
        if c.kind == "millionaire"
        else "Fan Points"
        if c.kind == "fanwars"
        else "prediction points",
        "provisional": c.status not in {"final", "no_contest", "canceled"},
        "total": total,
        "data": rows,
        "your_rank": row_read(mine) if mine else None,
        "school_standings": school_standings(
            db, c, metric=metric, conference=conference, season=season
        )
        if c.kind == "fanwars"
        else [],
    }


def modes(db, user):
    r = core().ensure_round(
        db,
        core().settings.current_season_year,
        core().competition_week(core().settings.current_season_year, now()),
    )
    result = []
    for kind, name in KINDS.items():
        ids = [
            c.id
            for c in db.query(WeeklyChallenge)
            .join(
                ChallengeExperience,
                ChallengeExperience.challenge_id == WeeklyChallenge.id,
            )
            .filter(
                WeeklyChallenge.round_id == r.id,
                WeeklyChallenge.kind == kind,
                ChallengeExperience.enabled.is_(True),
                WeeklyChallenge.published_at.is_not(None),
            )
            if visible(db, c)
        ]
        count = (
            db.query(ChallengeEntry.id)
            .filter(
                ChallengeEntry.challenge_id.in_(ids),
                ChallengeEntry.status == "submitted",
            )
            .count()
        )
        competitions = [db.get(WeeklyChallenge, cid) for cid in ids]
        states = [state(db, c, r) for c in competitions]
        times = []
        for c in competitions:
            if state(db, c, r) != "Open":
                continue
            if c.kind == "fanwars":
                current_games = {g.id: g for g in core().games_for(db, c)}
                times.extend(
                    game_deadline(row, current_games[row.game_id])
                    for row in core().slate_rows(db, c)
                    if row.locked_at is None
                    and game_deadline(row, current_games[row.game_id]) > now()
                )
            elif deadline(db, c):
                times.append(deadline(db, c))
        result.append(
            {
                "kind": kind,
                "name": name,
                "description": DESCRIPTIONS[kind],
                "competitions": ids,
                "participants": count,
                "lock_at": min(times) if times else None,
                "server_now": now(),
                "state": "Open"
                if "Open" in states
                else "Final"
                if states and all(s == "Closed — Final" for s in states)
                else "In Progress"
                if any(
                    s.startswith("Closed — Live") or s.startswith("Closed — Results")
                    for s in states
                )
                else "Upcoming"
                if states
                else "Not published",
            }
        )
    return result


def record_event(db, user, kind, challenge_id=None, creator_slug=None, *, commit=True):
    from collegefootballfantasy_api.app.models.challenge_experience import (
        ChallengeAnalyticsPreference,
    )

    preference = db.get(ChallengeAnalyticsPreference, user.id)
    if preference is not None and not preference.enabled:
        return False
    c = db.get(WeeklyChallenge, challenge_id) if challenge_id else None
    if challenge_id and (
        not c or not c.published_at or c.kind in KINDS and not detail(db, c).enabled
    ):
        fail("NOT_FOUND", "Published competition not found.", 404)
    creator = (
        db.query(ChallengeCreator)
        .filter_by(slug=creator_slug, active=True, authorized=True)
        .one_or_none()
        if creator_slug
        else None
    )
    if creator_slug and creator is None:
        fail("NOT_FOUND", "Approved creator not found.", 404)
    # Daily per-account aggregation: no IP, cross-site identifier or raw browsing history.
    key = f"{kind}:{user.id}:{challenge_id or 0}:{creator.id if creator else 0}:{now().date()}"
    if db.query(ChallengeEvent.id).filter_by(dedupe_key=key).first() is None:
        try:
            with db.begin_nested():
                db.add(
                    ChallengeEvent(
                        dedupe_key=key,
                        challenge_id=challenge_id,
                        creator_id=creator.id if creator else None,
                        user_id=user.id,
                        event_type=kind,
                        at=now(),
                    )
                )
                db.flush()
        except IntegrityError:
            pass
    if (
        creator
        and kind == "referral_open"
        and now() - timedelta(hours=24)
        <= aware(user.created_at)
        <= now() + timedelta(seconds=60)
    ):
        signup_key = f"creator_signup:{user.id}"
        if not db.query(ChallengeEvent.id).filter_by(dedupe_key=signup_key).first():
            try:
                with db.begin_nested():
                    db.add(
                        ChallengeEvent(
                            dedupe_key=signup_key,
                            challenge_id=challenge_id,
                            creator_id=creator.id,
                            user_id=user.id,
                            event_type="signup",
                            at=now(),
                        )
                    )
                    db.flush()
            except IntegrityError:
                pass
    if commit:
        db.commit()
    return True


def analytics(db, c):
    q = db.query(ChallengeEvent).filter_by(challenge_id=c.id)
    entries = db.query(ChallengeEntry).filter_by(challenge_id=c.id)
    submitted = entries.filter_by(status="submitted").count()
    total = entries.count()
    r = db.get(ChallengeRound, c.round_id)
    users = [uid for (uid,) in entries.with_entities(ChallengeEntry.user_id)]
    returning = (
        db.query(ChallengeEntry.user_id)
        .join(WeeklyChallenge)
        .join(ChallengeRound)
        .filter(
            ChallengeEntry.user_id.in_(users),
            WeeklyChallenge.kind == c.kind,
            ChallengeRound.season == r.season,
            ChallengeRound.week < r.week,
            ChallengeEntry.status == "submitted",
        )
        .distinct()
        .count()
    )
    creator = detail(db, c).creator_id
    return {
        "challenge_id": c.id,
        "views": q.filter_by(event_type="view").count(),
        "shares": q.filter_by(event_type="share").count(),
        "unique_participants": total,
        "submitted_entries": submitted,
        "completion_rate": round(submitted / total, 4) if total else 0,
        "returning_participants": returning,
        "creator_link_visitors": db.query(ChallengeEvent.user_id)
        .filter_by(creator_id=creator, event_type="referral_open")
        .distinct()
        .count()
        if creator
        else 0,
        "attributed_signups": db.query(ChallengeEvent.id)
        .filter_by(creator_id=creator, event_type="signup")
        .count()
        if creator
        else 0,
    }


def read_challenge(db, c, user, *, admin=False, include_details=True):
    r = db.get(ChallengeRound, c.round_id)
    x = detail(db, c)
    public = admin or c.published_at is not None
    if not admin and not visible(db, c):
        fail("NOT_FOUND", "This competition is temporarily unavailable.", 404, c)
    config = c.config if public else {}
    games = {g.id: g for g in core().games_for(db, c)}
    display = (
        [
            {
                **row.snapshot,
                "status": games[row.game_id].schedule_status,
                "home_points": games[row.game_id].home_points,
                "away_points": games[row.game_id].away_points,
            }
            for row in core().slate_rows(db, c)
        ]
        if public and include_details
        else []
    )
    extra = read(db, c, user, admin=admin, include_details=include_details)
    return {
        "id": c.id,
        "round_id": r.id,
        "season": r.season,
        "week": r.week,
        "kind": c.kind,
        "name": KINDS[c.kind],
        "state": state(db, c, r),
        "settlement_status": c.status,
        "version": c.version,
        "rules_version": c.rules_version,
        "rules": RULES[c.kind].format(
            correct_points=config.get("correct_points", 10),
            minimum_fans=config.get("minimum_fans", 3),
        ),
        "lock_at": deadline(db, c) if public else None,
        "server_now": now(),
        "published_at": c.published_at,
        "scoring_version": config.get("scoring_version"),
        "scoring_rules": config.get("scoring_rules"),
        "games": display,
        "players": [
            {
                **p.snapshot,
                "image_url": p.snapshot.get("image_url")
                if core().settings.player_headshots_enabled
                else None,
            }
            for p in db.query(ChallengePoolPlayer).filter_by(challenge_id=c.id)
        ]
        if public and include_details
        else [],
        "featured_game_id": None,
        "underdogs": [],
        "entry": core().entry_for(db, c, user.id),
        "cancellation_reason": c.cancellation_reason,
        "draft_config": None,
        "sponsor": core().weekly_challenge_sponsor(season=r.season, week=r.week),
        "participant_count": extra["participants"],
        "experience": extra,
    }


def published_projections(db, c, player_ids):
    import math
    from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
    r = db.get(ChallengeRound, c.round_id)
    # Reuse the same version precedence as player cards, rosters and the projection API.
    # A published correction or locked snapshot must outrank an older FINAL row.
    rows = db.scalars(current_published_projections_query(season=r.season, week=r.week, player_ids=player_ids))
    return {p.player_id: p.fantasy_points for p in rows
            if p.fantasy_points is not None and math.isfinite(p.fantasy_points)}


def notification_eligible(db, row, user):
    c = db.get(WeeklyChallenge, (row.payload or {}).get("challenge_id"))
    if (
        not c
        or c.kind not in KINDS
        or not c.published_at
        or not visible(db, c)
        or c.status == "canceled"
    ):
        return False
    e = core().entry_for(db, c, user.id)
    if row.event_type == "CHALLENGE_RESULT":
        s = (
            db.query(ChallengeScore).filter_by(entry_id=e.id).one_or_none()
            if e
            else None
        )
        return bool(
            s
            and s.status == "final"
            and s.source_hash == (row.payload or {}).get("source_hash")
        )
    end = deadline(db, c)
    if (
        not end
        or now() >= end
        or end.isoformat() != (row.payload or {}).get("deadline")
    ):
        return False
    if e:
        return e.status in {"draft", "submitted"}
    if c.kind == "survivor":
        return (
            _series_state(
                db, detail(db, c), user.id, db.get(ChallengeRound, c.round_id).week
            )[2]
            == "active"
        )
    return False


def queue_results(db, c, scores):
    from collegefootballfantasy_api.app.services.notification_service import (
        queue_notification_event,
    )

    for e, s in scores:
        if s.status != "final":
            continue
        queue_notification_event(
            db,
            league_id=None,
            user_id=e.user_id,
            event_type="CHALLENGE_RESULT",
            event_key=f"challenge-result:{c.id}:{e.user_id}:{s.source_hash}",
            payload={"challenge_id": c.id, "source_hash": s.source_hash},
            title=f"{KINDS[c.kind]} results are in",
            body="Your official challenge result is ready. Open CFFB to view your points and standing.",
            channels=("in_app", "push"),
        )


def queue_reminders(db):
    from collegefootballfantasy_api.app.services.notification_service import (
        queue_notification_event,
    )

    candidates = (
        db.query(WeeklyChallenge)
        .join(
            ChallengeExperience, ChallengeExperience.challenge_id == WeeklyChallenge.id
        )
        .filter(
            WeeklyChallenge.published_at.is_not(None),
            WeeklyChallenge.status.in_(["published", "processing"]),
            ChallengeExperience.enabled.is_(True),
        )
        .order_by(WeeklyChallenge.id.desc())
        .limit(50)
    )
    for c in candidates:
        r = db.get(ChallengeRound, c.round_id)
        if state(db, c, r) != "Open":
            continue
        end = deadline(db, c)
        if not end or not now() < end <= now() + timedelta(minutes=30):
            continue
        users = {
            uid
            for (uid,) in db.query(ChallengeEntry.user_id).filter(
                ChallengeEntry.challenge_id == c.id,
                ChallengeEntry.status.in_(["draft", "submitted"]),
            )
        }
        if c.kind == "survivor":
            users.update(
                e.user_id
                for e in db.query(ChallengeSurvivorEnrollment).filter_by(
                    series_id=detail(db, c).series_id
                )
                if _series_state(db, detail(db, c), e.user_id, r.week)[2] == "active"
            )
        for uid in users:
            row = queue_notification_event(
                db,
                league_id=None,
                user_id=uid,
                event_type="CHALLENGE_REMINDER",
                event_key=f"challenge-reminder:{c.id}:{uid}:{int(end.timestamp())}",
                payload={"challenge_id": c.id, "deadline": end.isoformat()},
                title=f"{KINDS[c.kind]} locks soon",
                body="Review and submit your official entry before the published deadline.",
                channels=("in_app", "push"),
            )
            row.expires_at = end
    db.commit()


def config_projection(c):
    return c.config.get("projection_snapshot", {})


def visible(db, c):
    x = detail(db, c)
    if not x.enabled:
        return False
    if c.kind != "creator" or c.status in {"final", "no_contest", "canceled"}:
        return True
    creator = db.get(ChallengeCreator, x.creator_id)
    return bool(creator and creator.active and creator.authorized)
