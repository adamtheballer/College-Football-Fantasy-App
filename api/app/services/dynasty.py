"""Isolated 2027 preview; transaction ownership stays at the route boundary."""

from datetime import date, datetime, timezone
from fractions import Fraction
import secrets
from random import SystemRandom

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.dynasty import (
    DynastyFranchise,
    DynastyLeague,
    DynastyPickAsset,
    DynastyPlayerSeason,
    DynastySeason,
    DynastyTrade,
    DynastyRoster,
)
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.dynasty import (
    DynastyCreate,
    DynastyFinish,
    DynastyState,
)
from collegefootballfantasy_api.app.services.draft_service import (
    draft_pick_team_for_number,
)
from collegefootballfantasy_api.app.services.player_pool_filters import (
    ELIGIBLE_FANTASY_POSITIONS,
    is_approved_fantasy_school,
)


def fail(detail: str, status: int = 409):
    raise HTTPException(status_code=status, detail=detail)


def context(db: Session, league_id: int, user: User, *, write: bool = False):
    query = (
        select(DynastyLeague)
        .where(DynastyLeague.league_id == league_id)
        .execution_options(populate_existing=True)
    )
    config = db.scalar(query.with_for_update() if write else query)
    if config is None:
        fail("dynasty league not found", 404)
    if not db.scalar(
        select(DynastyFranchise.id).where(
            DynastyFranchise.league_id == league_id,
            DynastyFranchise.owner_user_id == user.id,
        )
    ):
        fail("league membership required", 403)
    league = config
    season = db.get(
        DynastySeason, (league_id, config.current_season), populate_existing=True
    )
    return config, league, season


def commissioner(league: DynastyLeague, user: User):
    if league.commissioner_user_id != user.id:
        fail("commissioner only", 403)


def team(db: Session, league_id: int, team_id: int) -> DynastyFranchise:
    row = db.scalar(
        select(DynastyFranchise)
        .where(DynastyFranchise.league_id == league_id, DynastyFranchise.id == team_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        fail("team is outside this dynasty league", 422)
    return row


def owned_team(
    db: Session, league_id: int, team_id: int, user: User
) -> DynastyFranchise:
    row = team(db, league_id, team_id)
    if row.owner_user_id != user.id:
        fail("team ownership required", 403)
    return row


def franchises(db: Session, league_id: int) -> list[DynastyFranchise]:
    return db.scalars(
        select(DynastyFranchise)
        .where(DynastyFranchise.league_id == league_id)
        .order_by(DynastyFranchise.id)
    ).all()


def mint_picks(db: Session, config: DynastyLeague, teams: list[DynastyFranchise]):
    existing = {
        (p.season, p.round_number, p.original_team_id)
        for p in db.scalars(
            select(DynastyPickAsset).where(
                DynastyPickAsset.league_id == config.league_id
            )
        )
    }
    for year in range(
        config.current_season, config.current_season + config.future_pick_years + 1
    ):
        rounds = (
            config.startup_rounds
            if year == config.startup_season
            else config.freshman_rounds
        )
        for round_number in range(1, rounds + 1):
            for franchise in teams:
                if (year, round_number, franchise.id) not in existing:
                    db.add(
                        DynastyPickAsset(
                            league_id=config.league_id,
                            season=year,
                            round_number=round_number,
                            original_team_id=franchise.id,
                            owner_team_id=franchise.id,
                        )
                    )
    db.flush()


def create_league(db: Session, user: User, payload: DynastyCreate):
    name = payload.name.strip()
    if len(name) < 3:
        fail("league name is too short", 422)
    config = DynastyLeague(
        name=name,
        startup_season=payload.season,
        current_season=payload.season,
        commissioner_user_id=user.id,
        max_teams=payload.team_count,
        invite_code=secrets.token_hex(10).upper(),
        roster_limit=payload.roster_limit,
        startup_rounds=payload.startup_rounds,
        freshman_rounds=payload.freshman_rounds,
        future_pick_years=payload.future_pick_years,
    )
    db.add(config)
    db.flush()
    league = config
    franchise = DynastyFranchise(
        league_id=league.league_id,
        name=f"{(user.first_name or 'Manager')[:72]} Dynasty",
        owner_user_id=user.id,
    )
    db.add(franchise)
    db.add(
        DynastySeason(
            league_id=league.league_id, season=payload.season, draft_kind="startup"
        )
    )
    db.flush()
    mint_picks(db, config, [franchise])
    return league.league_id


def join_league(db: Session, user: User, invite_code: str, name: str):
    league = db.scalar(
        select(DynastyLeague).where(
            DynastyLeague.invite_code == invite_code.strip().upper(),
            DynastyLeague.startup_season >= 2027,
        )
    )
    if league is None:
        fail("dynasty invite not found", 404)
    config = db.scalar(
        select(DynastyLeague)
        .where(DynastyLeague.league_id == league.league_id)
        .with_for_update()
    )
    if config is None:
        fail("dynasty league not found", 404)
    if db.scalar(
        select(DynastyFranchise.id).where(
            DynastyFranchise.league_id == league.league_id,
            DynastyFranchise.owner_user_id == user.id,
        )
    ):
        return league.league_id
    season = db.get(DynastySeason, (league.league_id, config.current_season))
    teams = franchises(db, league.league_id)
    if season.status != "scheduled" or season.draft_kind != "startup":
        fail("dynasty membership is locked after startup begins")
    if len(teams) >= league.max_teams:
        fail("league is full")
    if not name.strip() or any(
        t.name.casefold() == name.strip().casefold() for t in teams
    ):
        fail("choose a unique team name", 422)
    franchise = DynastyFranchise(
        league_id=league.league_id, name=name.strip(), owner_user_id=user.id
    )
    db.add(franchise)
    db.flush()
    mint_picks(db, config, [franchise])
    return league.league_id


def review_catalog(db: Session, facts):
    keys = [(r.player_id, r.season) for r in facts]
    if len(keys) != len(set(keys)):
        fail("duplicate catalog fact", 422)
    for item in facts:
        player = db.get(Player, item.player_id)
        if player is None:
            fail("catalog player not found", 404)
        if (
            player.position not in ELIGIBLE_FANTASY_POSITIONS
            or not is_approved_fantasy_school(item.school)
        ):
            fail("player is outside the approved fantasy universe", 422)
    for item in facts:
        row = db.get(DynastyPlayerSeason, (item.player_id, item.season))
        if row is None:
            row = DynastyPlayerSeason(player_id=item.player_id, season=item.season)
            db.add(row)
        for key, value in item.model_dump().items():
            setattr(row, key, str(value) if key == "source_url" else value)
        row.reviewed = True
    db.flush()


def dynasty_value(fact: DynastyPlayerSeason) -> dict:
    factors = {
        "FR": 1.2,
        "RSFR": 1.15,
        "SO": 1.1,
        "RSSO": 1.08,
        "JR": 1.0,
        "RSJR": 0.98,
        "SR": 0.9,
        "RSSR": 0.85,
        "GR": 0.8,
        "UNKNOWN": 1.0,
    }
    cutoff = date(fact.season, 8, 1)
    age = (
        cutoff.year
        - fact.birth_date.year
        - ((cutoff.month, cutoff.day) < (fact.birth_date.month, fact.birth_date.day))
        if fact.birth_date
        else None
    )
    age_factor = (
        round(max(0.8, min(1.1, 1 + (21 - age) * 0.02)), 4) if age is not None else 1.0
    )
    class_factor = factors[fact.academic_class]
    return {
        "policy_version": "dynasty_preview_v1",
        "provisional": True,
        "base_value": fact.base_value,
        "academic_class": fact.academic_class,
        "class_factor": class_factor,
        "age": age,
        "age_factor": age_factor,
        "estimate": (
            round(fact.base_value * class_factor * age_factor, 2)
            if fact.base_value is not None
            else None
        ),
    }


def pool(db: Session, config: DynastyLeague, season: DynastySeason):
    owned = select(DynastyRoster.player_id).where(
        DynastyRoster.league_id == config.league_id
    )
    consumed = select(DynastyPickAsset.player_id).where(
        DynastyPickAsset.league_id == config.league_id,
        DynastyPickAsset.season == season.season,
        DynastyPickAsset.player_id.is_not(None),
    )
    query = (
        select(Player, DynastyPlayerSeason)
        .join(DynastyPlayerSeason, DynastyPlayerSeason.player_id == Player.id)
        .where(
            DynastyPlayerSeason.season == season.season,
            DynastyPlayerSeason.eligible.is_(True),
            DynastyPlayerSeason.reviewed.is_(True),
            Player.position.in_(ELIGIBLE_FANTASY_POSITIONS),
            Player.id.not_in(owned),
            Player.id.not_in(consumed),
        )
    )
    if season.draft_kind == "freshman":
        query = query.where(
            DynastyPlayerSeason.entry_season == season.season,
            DynastyPlayerSeason.academic_class == "FR",
        )
    if season.status != "scheduled":
        query = query.where(Player.id.in_([r["player_id"] for r in season.pool_json]))
    result = [
        {
            "player_id": p.id,
            "name": p.name,
            "school": f.school,
            "position": p.position,
            "entry_season": f.entry_season,
            "source_url": f.source_url,
            "value": dynasty_value(f),
        }
        for p, f in db.execute(query)
    ]
    return sorted(
        result,
        key=lambda r: (
            r["value"]["estimate"] is None,
            -(r["value"]["estimate"] or 0),
            r["name"],
            r["player_id"],
        ),
    )


def annual_order(results: list[dict]) -> list[int]:
    def record(r):
        games = r["wins"] + r["losses"] + r["ties"]
        return Fraction(2 * r["wins"] + r["ties"], 2 * games) if games else Fraction(0)

    return [
        r["team_id"]
        for r in sorted(
            results,
            key=lambda r: (
                r["playoff_finish"] is not None,
                -(r["playoff_finish"] or 0),
                record(r),
                r["points_for"],
                r["team_id"],
            ),
        )
    ]


def start(db: Session, config, league, season, user):
    commissioner(league, user)
    if season.status != "scheduled":
        return  # A retry must never reroll the order or reset the cursor.
    teams = franchises(db, league.league_id)
    if len(teams) != league.max_teams:
        fail("fill every franchise before starting")
    candidates = pool(db, config, season)
    rounds = (
        config.startup_rounds
        if season.draft_kind == "startup"
        else config.freshman_rounds
    )
    if len(candidates) < len(teams) * rounds:
        fail("not enough reviewed eligible players for every draft pick")
    for t in teams:
        incoming = db.scalar(
            select(func.count())
            .select_from(DynastyPickAsset)
            .where(
                DynastyPickAsset.league_id == config.league_id,
                DynastyPickAsset.season == season.season,
                DynastyPickAsset.owner_team_id == t.id,
            )
        )
        if (
            db.scalar(
                select(func.count())
                .select_from(DynastyRoster)
                .where(DynastyRoster.team_id == t.id)
            )
            + incoming
            > config.roster_limit
        ):
            fail("make roster space before starting the draft")
    order = list(season.order_json)
    if season.draft_kind == "startup":
        order = [t.id for t in teams]
        SystemRandom().shuffle(order)
    if set(order) != {t.id for t in teams} or len(order) != len(teams):
        fail("complete prior-season results are required")
    season.order_json = order
    season.pool_json = [
        {
            "player_id": p["player_id"],
            "entry_season": p["entry_season"],
            "academic_class": p["value"]["academic_class"],
            "source_url": p["source_url"],
        }
        for p in candidates
    ]
    by_id = {t.id: t for t in teams}
    ordered = [by_id[tid] for tid in order]
    assets = {
        (p.round_number, p.original_team_id): p
        for p in db.scalars(
            select(DynastyPickAsset).where(
                DynastyPickAsset.league_id == league.league_id,
                DynastyPickAsset.season == season.season,
            )
        )
    }
    for number in range(1, len(teams) * rounds + 1):
        rnd, _, origin = draft_pick_team_for_number(ordered, number)
        assets[(rnd, origin.id)].overall_pick = number
    season.status = "drafting"
    db.flush()


def pick(db: Session, config, season, pick_id: int, player_id: int, user):
    asset = db.scalar(
        select(DynastyPickAsset)
        .where(
            DynastyPickAsset.id == pick_id,
            DynastyPickAsset.league_id == config.league_id,
        )
        .execution_options(populate_existing=True)
    )
    if asset is None:
        fail("pick not found", 404)
    owned_team(db, config.league_id, asset.owner_team_id, user)
    if asset.player_id is not None:
        if asset.player_id == player_id:
            return  # Idempotent retry, even after the draft completed.
        fail("pick has already been used")
    if (
        season.status != "drafting"
        or asset.season != season.season
        or asset.overall_pick != season.pick_cursor + 1
    ):
        fail("pick is not on the clock")
    if player_id not in {r["player_id"] for r in pool(db, config, season)}:
        fail("player is not eligible for this draft")
    count = db.scalar(
        select(func.count())
        .select_from(DynastyRoster)
        .where(DynastyRoster.team_id == asset.owner_team_id)
    )
    if count >= config.roster_limit:
        fail("roster is full")
    db.add(
        DynastyRoster(
            league_id=config.league_id, team_id=asset.owner_team_id, player_id=player_id
        )
    )
    asset.player_id, asset.picked_at = player_id, datetime.now(timezone.utc)
    season.pick_cursor += 1
    rounds = (
        config.startup_rounds
        if season.draft_kind == "startup"
        else config.freshman_rounds
    )
    if season.pick_cursor == len(season.order_json) * rounds:
        season.status = "complete"
    db.flush()


def validate_assets(db, config, assets):
    keys = [(a["kind"], a["id"]) for a in assets]
    if len(keys) != len(set(keys)):
        fail("duplicate trade asset", 422)
    records = []
    for asset in assets:
        team(db, config.league_id, asset["from_team_id"])
        if asset["kind"] == "pick":
            row = db.scalar(
                select(DynastyPickAsset)
                .where(
                    DynastyPickAsset.id == asset["id"],
                    DynastyPickAsset.league_id == config.league_id,
                )
                .execution_options(populate_existing=True)
            )
            if (
                row is None
                or row.owner_team_id != asset["from_team_id"]
                or row.player_id is not None
                or not config.current_season
                <= row.season
                <= config.current_season + config.future_pick_years
            ):
                fail("trade pick is no longer owned or available")
        else:
            row = db.scalar(
                select(DynastyRoster)
                .where(
                    DynastyRoster.league_id == config.league_id,
                    DynastyRoster.player_id == asset["id"],
                    DynastyRoster.team_id == asset["from_team_id"],
                )
                .execution_options(populate_existing=True)
            )
            if row is None:
                fail("trade player is no longer owned")
        records.append(row)
    return records


def propose_trade(db, config, payload, user):
    if (
        db.get(DynastySeason, (config.league_id, config.current_season)).status
        == "closed"
    ):
        fail("roll over the closed season before trading")
    owned_team(db, config.league_id, payload.from_team_id, user)
    team(db, config.league_id, payload.to_team_id)
    if payload.from_team_id == payload.to_team_id:
        fail("trade requires two different teams", 422)
    assets = [
        {**a.model_dump(), "from_team_id": source}
        for source, items in (
            (payload.from_team_id, payload.give),
            (payload.to_team_id, payload.receive),
        )
        for a in items
    ]
    validate_assets(db, config, assets)
    row = DynastyTrade(
        league_id=config.league_id,
        from_team_id=payload.from_team_id,
        to_team_id=payload.to_team_id,
        assets_json=assets,
    )
    db.add(row)
    db.flush()


def settle_trade(db, config, trade_id, action, user):
    trade = db.scalar(
        select(DynastyTrade)
        .where(DynastyTrade.id == trade_id, DynastyTrade.league_id == config.league_id)
        .execution_options(populate_existing=True)
    )
    if trade is None:
        fail("trade not found", 404)
    owned_team(
        db,
        config.league_id,
        trade.from_team_id if action == "cancel" else trade.to_team_id,
        user,
    )
    target_status = {"accept": "accepted", "cancel": "cancelled", "reject": "rejected"}[
        action
    ]
    if trade.status == target_status:
        return
    if trade.status != "pending":
        fail("trade is no longer pending")
    if action != "accept":
        trade.status = target_status
        return
    if (
        db.get(DynastySeason, (config.league_id, config.current_season)).status
        == "closed"
    ):
        fail("roll over the closed season before trading")
    rows = validate_assets(db, config, trade.assets_json)
    destinations = [
        (
            trade.to_team_id
            if a["from_team_id"] == trade.from_team_id
            else trade.from_team_id
        )
        for a in trade.assets_json
    ]
    for tid in (trade.from_team_id, trade.to_team_id):
        current = db.scalar(
            select(func.count())
            .select_from(DynastyRoster)
            .where(DynastyRoster.team_id == tid)
        )
        outgoing = sum(
            a["kind"] == "player" and a["from_team_id"] == tid
            for a in trade.assets_json
        )
        incoming = sum(
            a["kind"] == "player" and destination == tid
            for a, destination in zip(trade.assets_json, destinations)
        )
        if current - outgoing + incoming > config.roster_limit:
            fail("trade exceeds roster capacity")
    for asset, row, destination in zip(trade.assets_json, rows, destinations):
        if asset["kind"] == "pick":
            row.owner_team_id = destination
        else:
            row.team_id = destination
    db.flush()
    trade.status = "accepted"


def close_season(db, config, league, season, user, results: list[DynastyFinish]):
    commissioner(league, user)
    data = [r.model_dump() for r in results]
    if season.status == "closed" and season.results_json == data:
        return
    if season.status != "complete":
        fail("complete the draft before closing the season")
    if {r.team_id for r in results} != {
        t.id for t in franchises(db, league.league_id)
    } or len(results) != len({r.team_id for r in results}):
        fail("provide one result for every franchise", 422)
    playoff = [r for r in results if r.playoff_finish is not None]
    if playoff and (
        sum(r.playoff_finish == 1 for r in playoff) != 1
        or (len(playoff) > 1 and sum(r.playoff_finish == 2 for r in playoff) != 1)
    ):
        fail("playoff results require one champion and one runner-up", 422)
    season.results_json = data
    season.roster_snapshot_json = [
        {"player_id": r.player_id, "team_id": r.team_id}
        for r in db.scalars(
            select(DynastyRoster).where(DynastyRoster.league_id == league.league_id)
        )
    ]
    season.status = "closed"


def rollover(db, config, league, season, user):
    commissioner(league, user)
    if season.status != "closed":
        fail("close the current season before rollover")
    year = season.season + 1
    if year + config.future_pick_years > 2100:
        fail("season exceeds supported horizon", 422)
    exits = []
    for entry in db.scalars(
        select(DynastyRoster).where(DynastyRoster.league_id == league.league_id)
    ).all():
        fact = db.get(DynastyPlayerSeason, (entry.player_id, year))
        if fact is not None and fact.reviewed and not fact.eligible:
            exits.append(
                {
                    "player_id": entry.player_id,
                    "team_id": entry.team_id,
                    "reason": "reviewed departure",
                    "source_url": fact.source_url,
                }
            )
            db.delete(entry)
    db.add(
        DynastySeason(
            league_id=league.league_id,
            season=year,
            draft_kind="freshman",
            order_json=annual_order(season.results_json),
            departures_json=exits,
        )
    )
    config.current_season = year
    db.flush()
    mint_picks(db, config, franchises(db, league.league_id))


def drop(db, config, season, entry_id, user):
    if season.status == "closed":
        fail("roll over the closed season before dropping players")
    entry = db.scalar(
        select(DynastyRoster).where(
            DynastyRoster.id == entry_id, DynastyRoster.league_id == config.league_id
        )
    )
    if entry is None:
        fail("roster entry not found", 404)
    owned_team(db, config.league_id, entry.team_id, user)
    season.departures_json = [
        *season.departures_json,
        {
            "player_id": entry.player_id,
            "team_id": entry.team_id,
            "reason": "owner drop",
        },
    ]
    db.delete(entry)
    db.flush()


def state(db: Session, league_id: int, user: User) -> DynastyState:
    config, league, season = context(db, league_id, user)
    picks = db.scalars(
        select(DynastyPickAsset)
        .where(
            DynastyPickAsset.league_id == league_id,
            DynastyPickAsset.season >= config.current_season,
        )
        .order_by(
            DynastyPickAsset.season, DynastyPickAsset.overall_pick, DynastyPickAsset.id
        )
    ).all()
    next_pick = next(
        (
            p.id
            for p in picks
            if season.status == "drafting"
            and p.season == season.season
            and p.overall_pick == season.pick_cursor + 1
        ),
        None,
    )
    rosters = [
        {
            "id": r.id,
            "team_id": r.team_id,
            "player_id": p.id,
            "name": p.name,
            "position": p.position,
            "school": f.school if f and f.reviewed else None,
            "value": dynasty_value(f) if f and f.reviewed else None,
        }
        for r, p, f in db.execute(
            select(DynastyRoster, Player, DynastyPlayerSeason)
            .join(Player, Player.id == DynastyRoster.player_id)
            .outerjoin(
                DynastyPlayerSeason,
                (DynastyPlayerSeason.player_id == Player.id)
                & (DynastyPlayerSeason.season == config.current_season),
            )
            .where(DynastyRoster.league_id == league_id)
            .order_by(DynastyRoster.team_id, DynastyRoster.id)
        )
    ]
    return DynastyState(
        league_id=league_id,
        name=league.name,
        commissioner_user_id=league.commissioner_user_id,
        invite_code=(
            league.invite_code if user.id == league.commissioner_user_id else None
        ),
        startup_season=config.startup_season,
        current_season=config.current_season,
        roster_limit=config.roster_limit,
        startup_rounds=config.startup_rounds,
        freshman_rounds=config.freshman_rounds,
        future_pick_years=config.future_pick_years,
        draft_kind=season.draft_kind,
        status=season.status,
        pick_cursor=season.pick_cursor,
        order=season.order_json,
        next_pick_id=next_pick,
        teams=[
            {"id": t.id, "name": t.name, "owner_user_id": t.owner_user_id}
            for t in franchises(db, league_id)
        ],
        rosters=rosters,
        picks=picks,
        trades=db.scalars(
            select(DynastyTrade)
            .where(DynastyTrade.league_id == league_id)
            .order_by(DynastyTrade.id.desc())
            .limit(100)
        ).all(),
        departures=season.departures_json,
    )
