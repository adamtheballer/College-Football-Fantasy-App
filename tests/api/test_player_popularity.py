from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_player_event import LeaguePlayerEvent
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_popularity_snapshot import PlayerHotPickupMetric
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.league_player_history import EVENT_FREE_AGENT_ADDED, EVENT_WAIVER_CLAIMED
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
from collegefootballfantasy_api.app.services.player_popularity import (
    hot_pickup_counts_for_ids,
    player_popularity_for_ids,
    publish_player_popularity_snapshot,
)


def _canonical_player(name: str) -> Player:
    return Player(
        name=name,
        position="WR",
        school="Texas",
        sheet_source_sheet_id="canonical-preseason:2026:popularity-test",
        sheet_projected_season_points=200.0,
    )


def _completed_league(db_session, owner: User, name: str) -> tuple[League, Team]:
    league = League(
        name=name,
        commissioner_user_id=owner.id,
        season_year=2026,
        platform="custom",
        status="post_draft",
    )
    db_session.add(league)
    db_session.flush()
    db_session.add(Draft(league_id=league.id, draft_datetime_utc=datetime(2026, 8, 1, tzinfo=timezone.utc), status="completed"))
    team = Team(league_id=league.id, name=f"{name} team", owner_user_id=owner.id, owner_name=owner.first_name)
    db_session.add(team)
    db_session.flush()
    return league, team


def test_daily_snapshot_uses_completed_league_cohort_and_distinguishes_missing_start_samples(db_session):
    now = datetime(2026, 9, 5, 7, tzinfo=timezone.utc)
    owner = User(email="popularity@example.com", first_name="Popularity", password_hash="x", api_token="popularity")
    db_session.add(owner)
    db_session.flush()
    first_league, first_team = _completed_league(db_session, owner, "First popular")
    second_league, second_team = _completed_league(db_session, owner, "Second popular")
    excluded = League(name="Pre-draft excluded", season_year=2026, platform="custom", status="pre_draft")
    db_session.add(excluded)
    first = _canonical_player("Popular Starter")
    second = _canonical_player("Popular Bench")
    unplayed = _canonical_player("No kickoff sample")
    db_session.add_all((first, second, unplayed))
    db_session.flush()
    db_session.add_all(
        (
            RosterEntry(league_id=first_league.id, team_id=first_team.id, player_id=first.id, slot="WR", slot_index=1, status="active"),
            RosterEntry(league_id=second_league.id, team_id=second_team.id, player_id=second.id, slot="BENCH", slot_index=1, status="active"),
            LineupWeekSnapshot(
                league_id=first_league.id,
                team_id=first_team.id,
                player_id=first.id,
                season=2026,
                week=calendar_cfb_week(2026, now),
                slot="WR",
                is_starter=True,
                locked_at=now,
            ),
            LineupWeekSnapshot(
                league_id=second_league.id,
                team_id=second_team.id,
                player_id=second.id,
                season=2026,
                week=calendar_cfb_week(2026, now),
                slot="BENCH",
                is_starter=False,
                locked_at=now,
            ),
            LeaguePlayerEvent(
                league_id=first_league.id,
                season=2026,
                player_id=first.id,
                event_type=EVENT_FREE_AGENT_ADDED,
                event_key="popularity-first-add",
                occurred_at=now - timedelta(hours=6),
                fantasy_team_id=first_team.id,
                player_name_snapshot=first.name,
                position_snapshot=first.position,
                school_snapshot=first.school,
            ),
            LeaguePlayerEvent(
                league_id=second_league.id,
                season=2026,
                player_id=second.id,
                event_type=EVENT_WAIVER_CLAIMED,
                event_key="popularity-second-waiver",
                occurred_at=now - timedelta(hours=48),
                fantasy_team_id=second_team.id,
                player_name_snapshot=second.name,
                position_snapshot=second.position,
                school_snapshot=second.school,
            ),
        )
    )
    db_session.commit()

    snapshot = publish_player_popularity_snapshot(db_session, season=2026, now=now)
    assert snapshot.status == "published"
    popularity, metadata = player_popularity_for_ids(
        db_session, season=2026, player_ids={first.id, second.id, unplayed.id}
    )
    assert metadata.status == "fresh"
    assert popularity[first.id].rostered_percent == 50.0
    assert popularity[first.id].start_percent == 50.0
    assert popularity[second.id].rostered_percent == 50.0
    assert popularity[second.id].start_percent == 0.0
    # No kickoff snapshot means the display must not invent a 0% start rate.
    assert popularity[unplayed.id].start_percent is None

    day_counts, _ = hot_pickup_counts_for_ids(
        db_session, season=2026, window_hours=24, player_ids={first.id, second.id}
    )
    week_counts, _ = hot_pickup_counts_for_ids(
        db_session, season=2026, window_hours=168, player_ids={first.id, second.id}
    )
    assert day_counts == {first.id: 1}
    assert week_counts == {first.id: 1, second.id: 1}
    assert db_session.query(PlayerHotPickupMetric).filter(PlayerHotPickupMetric.snapshot_id == snapshot.id).count() == 3


def test_published_daily_snapshot_is_idempotent(db_session):
    now = datetime(2026, 9, 5, 7, tzinfo=timezone.utc)
    first = publish_player_popularity_snapshot(db_session, season=2026, now=now)
    second = publish_player_popularity_snapshot(db_session, season=2026, now=now + timedelta(minutes=5))
    assert first.id == second.id
