from datetime import datetime, timezone
import pytest

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services import player_season_rank


@pytest.fixture(autouse=True)
def rank_publication_clock(monkeypatch):
    # Existing history fixtures represent completed weeks after their reset.
    monkeypatch.setattr(player_season_rank, "calendar_cfb_week", lambda season: 15)


def test_completed_rank_is_published_only_after_reset(db_session, monkeypatch):
    from collegefootballfantasy_api.app.services import league_weeks
    from collegefootballfantasy_api.app.services.player_season_rank import season_positional_rank_for_player
    player = _rankable_player(name="Rank boundary", position="WR", school="Miami")
    db_session.add(player)
    db_session.flush()
    db_session.add(PlayerStat(player_id=player.id, season=2026, week=1, verified=True, stats={"fantasy_points": 20}))
    _finalize_week(db_session, week=1)
    db_session.commit()
    class Clock(datetime):
        current = datetime(2026, 9, 8, 11, 59, 59, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.current

    monkeypatch.setattr(league_weeks, "datetime", Clock)
    monkeypatch.setattr(player_season_rank, "calendar_cfb_week", league_weeks.calendar_cfb_week)
    assert season_positional_rank_for_player(db_session, player=player, season=2026) is None
    Clock.current = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    assert season_positional_rank_for_player(db_session, player=player, season=2026).fantasy_points == 20


def _rankable_player(*, name: str, position: str, school: str) -> Player:
    return Player(
        name=name,
        position=position,
        school=school,
        sheet_projected_season_points=180,
        sheet_source_sheet_id="canonical-preseason:2026:rank-test",
    )


def _finalize_week(db_session, *, week: int) -> None:
    league = League(name=f"Rank Finality {week}", season_year=2026)
    home = Team(league=league, name=f"Home {week}", owner_name=f"Home Owner {week}")
    away = Team(league=league, name=f"Away {week}", owner_name=f"Away Owner {week}")
    db_session.add_all([league, home, away])
    db_session.flush()
    db_session.add(
        Matchup(
            league_id=league.id,
            season=2026,
            week=week,
            home_team_id=home.id,
            away_team_id=away.id,
            status="final",
        )
    )


def test_player_card_exposes_only_finalized_cumulative_positional_rank(client, db_session):
    leader = _rankable_player(name="KJ Duff", position="WR", school="Miami")
    challenger = _rankable_player(name="Ryan Williams", position="WR", school="Alabama")
    qb = _rankable_player(name="Quarterback Example", position="QB", school="Texas")
    db_session.add_all([leader, challenger, qb])
    db_session.flush()
    db_session.add_all([
        PlayerStat(player_id=leader.id, season=2026, week=1, verified=True, stats={"fantasy_points": 30.0}),
        PlayerStat(player_id=challenger.id, season=2026, week=1, verified=True, stats={"fantasy_points": 20.0}),
        PlayerStat(player_id=qb.id, season=2026, week=1, verified=True, stats={"fantasy_points": 40.0}),
    ])
    db_session.commit()

    # Live or unprocessed Week 1 totals must never appear as season ranks.
    before_finality = client.get(f"/players/{leader.id}/card")
    assert before_finality.status_code == 200
    assert before_finality.json()["season_positional_rank"] is None

    _finalize_week(db_session, week=1)
    db_session.commit()

    after_week_one = client.get(f"/players/{leader.id}/card")
    assert after_week_one.status_code == 200
    assert after_week_one.json()["season_positional_rank"] == {
        "position": "WR",
        "rank": 1,
        "fantasy_points": 30.0,
        "through_week": 1,
    }

    db_session.add_all([
        PlayerStat(player_id=leader.id, season=2026, week=2, verified=True, stats={"fantasy_points": 10.0}),
        PlayerStat(player_id=challenger.id, season=2026, week=2, verified=True, stats={"fantasy_points": 25.0}),
    ])
    db_session.commit()

    # Week 2 is still partial: the visible rank remains based on Week 1 only.
    before_week_two_finality = client.get(f"/players/{leader.id}/card")
    assert before_week_two_finality.json()["season_positional_rank"] == {
        "position": "WR",
        "rank": 1,
        "fantasy_points": 30.0,
        "through_week": 1,
    }

    _finalize_week(db_session, week=2)
    db_session.commit()

    after_week_two = client.get(f"/players/{leader.id}/card")
    assert after_week_two.json()["season_positional_rank"] == {
        "position": "WR",
        "rank": 2,
        "fantasy_points": 40.0,
        "through_week": 2,
    }


def test_week_zero_opener_is_the_only_week_one_rank_input_for_early_team(client, db_session):
    early_team = _rankable_player(name="Florida State Receiver", position="WR", school="Florida State")
    normal_team = _rankable_player(name="SMU Receiver", position="WR", school="SMU")
    db_session.add_all([early_team, normal_team])
    db_session.add(
        Game(
            external_id="401864570",
            season=2026,
            week=0,
            home_team="Florida State",
            away_team="New Mexico State",
            schedule_status="final",
            start_date=datetime(2026, 8, 29, 23, tzinfo=timezone.utc),
            home_points=34,
            away_points=17,
        )
    )
    db_session.flush()
    db_session.add_all([
        PlayerStat(player_id=early_team.id, season=2026, week=0, verified=True, stats={"fantasy_points": 30.0}),
        # This is the later real-world Week 1 game. It is valid player-card
        # history, but must not be a second fantasy Week 1 rank contribution.
        PlayerStat(player_id=early_team.id, season=2026, week=1, verified=True, stats={"fantasy_points": 90.0}),
        PlayerStat(player_id=normal_team.id, season=2026, week=1, verified=True, stats={"fantasy_points": 35.0}),
    ])
    _finalize_week(db_session, week=1)
    db_session.commit()

    early_rank = client.get(f"/players/{early_team.id}/card")
    normal_rank = client.get(f"/players/{normal_team.id}/card")

    assert early_rank.json()["season_positional_rank"] == {
        "position": "WR", "rank": 2, "fantasy_points": 30.0, "through_week": 1,
    }
    assert normal_rank.json()["season_positional_rank"] == {
        "position": "WR", "rank": 1, "fantasy_points": 35.0, "through_week": 1,
    }
