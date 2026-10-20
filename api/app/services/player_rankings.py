"""Read-only performance rankings from the same verified facts as player charts."""
from collections import defaultdict
import math
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_league_or_404, require_league_member
from collegefootballfantasy_api.app.domain.stat_normalization import normalize_player_stats, aliases_for_position
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.player_rankings import RankedPlayer, RankingContext
from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_games_by_school, school_key
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week, season_week_one_start
from collegefootballfantasy_api.app.services.player_chart_publication import verified_fantasy_week_stats, points_from_verified_stats
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter, league_conference_player_filter, ELIGIBLE_FANTASY_POSITIONS


def completed_through_week(season: int, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    active = calendar_cfb_week(season)
    # The shared calendar clamps to Week 15; expose it after its final rollover.
    end = datetime.combine(season_week_one_start(season).date()+timedelta(weeks=15), time(8), tzinfo=ZoneInfo("America/New_York"))
    return 15 if active == 15 and now >= end else max(0, min(15, active-1))


def ranking_rows(db: Session, *, season: int, period: Literal["week", "season"] = "week",
                 week: int | None = None, league_id: int | None = None,
                 user: User | None = None) -> tuple[RankingContext, list[RankedPlayer]]:
    rules = None
    own_ids: set[int] = set()
    query = db.query(Player).filter(canonical_fantasy_player_filter(season))
    label = "Standard scoring"
    if league_id is not None:
        if user is None:
            raise HTTPException(401, "sign in required")
        league = get_league_or_404(db, league_id)
        require_league_member(db, league_id, user)
        if league.season_year != season:
            raise HTTPException(422, "Select the league's season to view its rankings.")
        ls = db.query(LeagueSettings).filter_by(league_id=league_id).first()
        rules = (ls.scoring_snapshot_json or ls.scoring_json) if ls else {}
        query = query.filter(league_conference_player_filter(ls.conference_codes if ls else None))
        own_ids = {pid for (pid,) in db.query(RosterEntry.player_id).join(Team, Team.id == RosterEntry.team_id)
                   .filter(RosterEntry.league_id == league_id, Team.owner_user_id == user.id)}
        label = f"{league.name} scoring"
    eligible = query.order_by(Player.id).all()
    eligible_ids = {p.id for p in eligible}
    # A legacy/ineligible roster player still appears in My players, but
    # cannot enter or change the eligible pool's positional rankings.
    players = eligible + db.query(Player).filter(Player.id.in_(own_ids - eligible_ids)).all() if own_ids - eligible_ids else eligible
    through = completed_through_week(season)
    games = db.query(Game).filter(Game.season == season, Game.week.between(0, through), Game.season_type == "regular").all()
    schools = {school_key(p.school) for p in eligible}
    available = sorted({max(1, g.week) for g in games
                        if (g.schedule_status or "").lower() in {"final", "post"}
                        and (school_key(g.home_team) in schools or school_key(g.away_team) in schools)})
    selected = week if week is not None else (max(available) if available else (through or None))
    if selected is not None and not 1 <= selected <= through:
        raise HTTPException(422, "Rankings are available only for completed fantasy weeks.")
    weeks = list(range(1, through + 1)) if period == "season" else ([selected] if selected else [])
    totals: dict[int, float] = defaultdict(float)
    raw: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    stat_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    verified: dict[int, int] = defaultdict(int)
    expected: dict[int, int] = defaultdict(int)
    updated = {}
    byes: set[int] = set()
    for w in weeks:
        schedule = {school_key(s.team_name): s for s in db.query(TeamSchedule).filter(TeamSchedule.season == season, TeamSchedule.week == w)}
        chosen = fantasy_games_by_school(db, season=season, week=w, games=games)
        facts = verified_fantasy_week_stats(db, season=season, week=w, players=players, final_games_only=True) if players else {}
        for p in players:
            game = chosen.get(school_key(p.school))
            if game is None:
                # Ambiguous duplicate games are not a bye. A school present
                # in the provider slate has an unresolved expected score.
                canonical = schedule.get(school_key(p.school))
                if canonical and canonical.is_bye:
                    byes.add(p.id)
                elif school_key(p.school) in chosen or canonical:
                    expected[p.id] += 1
                continue
            expected[p.id] += 1
            fact = facts.get(p.id)
            if fact is None:
                continue
            points = points_from_verified_stats(fact.stats, position=p.position, rules=rules)
            if points is None:
                continue
            totals[p.id] += points
            verified[p.id] += 1
            aliases = aliases_for_position(p.position)
            supplied_keys = {str(k).casefold() for k in fact.stats}
            for key, value in normalize_player_stats(fact.stats, p.position).items():
                supplied = any(alias.casefold() in supplied_keys for alias in aliases[key])
                if supplied and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                    raw[p.id][key] += float(value)
                    stat_counts[p.id][key] += 1
            if fact.updated_at:
                stamp = fact.updated_at.replace(tzinfo=timezone.utc) if fact.updated_at.tzinfo is None else fact.updated_at
                updated[p.id] = max(updated.get(p.id, stamp), stamp)
    rows = []
    for p in players:
        complete = verified[p.id] > 0 and verified[p.id] == expected[p.id]
        state = "ineligible" if p.id not in eligible_ids else "final" if complete else "bye" if period == "week" and expected[p.id] == 0 and p.id in byes else "pending"
        rows.append(RankedPlayer(id=p.id, name=p.name, school=p.school, position=p.position,
            image_url=p.espn_headshot_url or p.image_url, fantasy_points=round(totals[p.id], 2) if complete else None,
            position_rank=None, games=verified[p.id], missing_games=max(0, expected[p.id] - verified[p.id]),
            status=state, stats={key:value for key,value in raw[p.id].items() if stat_counts[p.id][key] == verified[p.id]}, updated_at=updated.get(p.id), on_my_roster=p.id in own_ids))
    rows.sort(key=lambda r: (r.fantasy_points is None, -(r.fantasy_points or 0), r.name.casefold(), r.id))
    for pos in ELIGIBLE_FANTASY_POSITIONS:
        last_points = None
        rank = 0
        for ordinal, row in enumerate([r for r in rows if r.position == pos and r.status == "final"], 1):
            if row.fantasy_points != last_points:
                rank = ordinal
                last_points = row.fantasy_points
            row.position_rank = rank
    context = RankingContext(season=season, period=period, week=selected if period == "week" else None,
        through_week=through, available_weeks=available, league_id=league_id, scoring_label=label,
        verified_players=sum(r.status == "final" for r in rows), pending_players=sum(r.status == "pending" for r in rows),
        updated_at=max(updated.values()) if updated else None)
    return context, rows
