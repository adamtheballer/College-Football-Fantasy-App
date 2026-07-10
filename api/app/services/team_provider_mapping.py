from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team_provider_id import TeamProviderId
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, resolve_power4_school


def normalized_provider(provider: str | None) -> str:
    return (provider or "sportsdata").strip().lower()


def canonical_team_for_school(school: str | None) -> str | None:
    if not school or not school.strip():
        return None
    return resolve_power4_school(school) or school.strip()


def upsert_team_provider_id(
    db: Session,
    *,
    canonical_school: str,
    provider: str,
    provider_team_id: str,
    provider_team_name: str | None = None,
    provider_abbreviation: str | None = None,
    match_confidence: int = 100,
    verified_by_user_id: int | None = None,
) -> TeamProviderId:
    provider_key = normalized_provider(provider)
    team_id = str(provider_team_id or "").strip()
    if not team_id:
        raise ValueError("provider_team_id is required")
    canonical_school_value = canonical_team_for_school(canonical_school)
    if not canonical_school_value:
        raise ValueError("canonical_school is required")

    row = (
        db.query(TeamProviderId)
        .filter(TeamProviderId.provider == provider_key, TeamProviderId.provider_team_id == team_id)
        .first()
    )
    if row is None:
        row = (
            db.query(TeamProviderId)
            .filter(TeamProviderId.canonical_school == canonical_school_value, TeamProviderId.provider == provider_key)
            .first()
        )
    if row is None:
        row = TeamProviderId(
            canonical_school=canonical_school_value,
            provider=provider_key,
            provider_team_id=team_id,
        )
        db.add(row)

    row.canonical_school = canonical_school_value
    row.provider = provider_key
    row.provider_team_id = team_id
    row.provider_team_name = provider_team_name
    row.provider_abbreviation = provider_abbreviation
    row.match_confidence = match_confidence
    row.verified_by_user_id = verified_by_user_id
    return row


def team_provider_ids_for_school(db: Session, canonical_school: str, provider: str | None = None) -> list[TeamProviderId]:
    query = db.query(TeamProviderId).filter(TeamProviderId.canonical_school == canonical_school)
    if provider:
        query = query.filter(TeamProviderId.provider == normalized_provider(provider))
    return query.all()


def _mapping_matches_game(mapping: TeamProviderId, game: Game) -> bool:
    if game.provider and normalized_provider(game.provider) != mapping.provider:
        return False
    return mapping.provider_team_id in {game.home_provider_team_id, game.away_provider_team_id}


def games_for_canonical_school(
    db: Session,
    *,
    canonical_school: str,
    season: int,
    week: int,
    provider: str | None = None,
) -> list[Game]:
    mappings = team_provider_ids_for_school(db, canonical_school, provider)
    if mappings:
        provider_ids = {mapping.provider_team_id for mapping in mappings}
        query = db.query(Game).filter(
            Game.season == season,
            Game.week == week,
            or_(Game.home_provider_team_id.in_(provider_ids), Game.away_provider_team_id.in_(provider_ids)),
        )
        if provider:
            query = query.filter(or_(Game.provider.is_(None), Game.provider == normalized_provider(provider)))
        rows = query.order_by(Game.start_date.asc()).all()
        return [game for game in rows if any(_mapping_matches_game(mapping, game) for mapping in mappings)]

    if resolve_power4_school(canonical_school):
        return []

    return (
        db.query(Game)
        .filter(Game.season == season, Game.week == week)
        .filter(or_(Game.home_team == canonical_school, Game.away_team == canonical_school))
        .order_by(Game.start_date.asc())
        .all()
    )


def games_for_player_school(db: Session, *, player: Player, season: int, week: int) -> list[Game]:
    canonical_school = canonical_team_for_school(player.school)
    if not canonical_school:
        return []
    return games_for_canonical_school(db, canonical_school=canonical_school, season=season, week=week)


@dataclass(frozen=True)
class LockReadinessReport:
    season: int
    week: int
    provider: str
    ready: bool
    checked_schools: list[str]
    unmapped_schools: list[str]
    missing_game_or_bye: list[str]
    bye_schools: list[str]
    missing_start_dates: list[dict[str, object]]

    def as_dict(self) -> dict[str, object]:
        return {
            "season": self.season,
            "week": self.week,
            "provider": self.provider,
            "ready": self.ready,
            "checked_schools": self.checked_schools,
            "unmapped_schools": self.unmapped_schools,
            "missing_game_or_bye": self.missing_game_or_bye,
            "bye_schools": self.bye_schools,
            "missing_start_dates": self.missing_start_dates,
        }


def _fantasy_schools(db: Session, league_id: int | None = None) -> list[str]:
    if league_id is not None:
        rows = (
            db.query(Player.school)
            .join(RosterEntry, RosterEntry.player_id == Player.id)
            .filter(RosterEntry.league_id == league_id)
            .distinct()
            .all()
        )
    else:
        rows = db.query(Player.school).distinct().all()
    schools = {canonical_team_for_school(row[0]) for row in rows}
    return sorted(school for school in schools if school)


def _bye_week_for_school(db: Session, *, canonical_school: str, season: int, provider: str) -> int | None:
    mappings = team_provider_ids_for_school(db, canonical_school, provider)
    if not mappings:
        return None
    provider_ids = {mapping.provider_team_id for mapping in mappings}
    rows = (
        db.query(Game.week)
        .filter(
            Game.season == season,
            Game.season_type == "regular",
            Game.week > 0,
            or_(Game.home_provider_team_id.in_(provider_ids), Game.away_provider_team_id.in_(provider_ids)),
        )
        .all()
    )
    played_weeks = {int(row[0]) for row in rows}
    if len(played_weeks) < 2:
        return None
    missing = sorted(set(range(min(played_weeks), max(played_weeks) + 1)) - played_weeks)
    return missing[0] if missing else None


def weekly_lock_readiness(
    db: Session,
    *,
    season: int,
    week: int,
    provider: str = "sportsdata",
    league_id: int | None = None,
) -> LockReadinessReport:
    provider_key = normalized_provider(provider)
    checked_schools = _fantasy_schools(db, league_id)
    unmapped_schools: list[str] = []
    missing_game_or_bye: list[str] = []
    bye_schools: list[str] = []
    missing_start_dates: list[dict[str, object]] = []

    for school in checked_schools:
        mappings = team_provider_ids_for_school(db, school, provider_key)
        if not mappings:
            unmapped_schools.append(school)
            continue

        games = games_for_canonical_school(db, canonical_school=school, season=season, week=week, provider=provider_key)
        if not games:
            if _bye_week_for_school(db, canonical_school=school, season=season, provider=provider_key) == week:
                bye_schools.append(school)
            else:
                missing_game_or_bye.append(school)
            continue

        for game in games:
            if game.start_date is None:
                missing_start_dates.append(
                    {
                        "school": school,
                        "game_id": game.id,
                        "external_id": game.external_id,
                        "home_team": canonical_school_name(game.home_team or "") or game.home_team,
                        "away_team": canonical_school_name(game.away_team or "") or game.away_team,
                    }
                )

    ready = not unmapped_schools and not missing_game_or_bye and not missing_start_dates
    return LockReadinessReport(
        season=season,
        week=week,
        provider=provider_key,
        ready=ready,
        checked_schools=checked_schools,
        unmapped_schools=sorted(unmapped_schools),
        missing_game_or_bye=sorted(missing_game_or_bye),
        bye_schools=sorted(bye_schools),
        missing_start_dates=missing_start_dates,
    )
