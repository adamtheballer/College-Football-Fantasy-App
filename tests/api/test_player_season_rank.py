from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team import Team


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
