from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.services.projections.engine import build_weekly_projections
from collegefootballfantasy_api.app.services.projections.production import calibrate_production_pace
from collegefootballfantasy_api.app.services.projections.usage import compute_usage_shares
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points


def candidate(position='TE', injury=None):
    player = Player(id=1, name='Verified Producer', school='Cincinnati', position=position)
    row = build_weekly_projections(players=[player], team_env_by_team={}, usage_by_player={},
        defense_by_team={}, player_stats={}, injuries_by_player={1: injury} if injury else {},
        opponent_by_team={}, season=2026, week=13)[0]
    return player, row


def test_established_receiving_production_without_target_field_drives_te_forecast():
    player, row = candidate()
    games = [dict(receptions=6, rec_yards=75, rec_tds=0.5) for _ in range(10)]
    assert calibrate_production_pace(row, player=player, games=games)
    assert 14 < row.fantasy_points < 17
    assert row.receptions > 5
    assert row.floor < row.fantasy_points < row.ceiling
    assert row.fantasy_points == calculate_fantasy_points(
        {key: getattr(row,key) for key in ['receptions','rec_yards','rec_tds','rush_yards','rush_tds']}, position='TE')
    assert row.baseline_games_played == 10


def test_tabb_like_rushing_and_receiving_production_both_survive_role_correction():
    player, row = candidate('RB')
    prior_carries = row.rush_attempts
    games = [dict(rushing_attempts=15, rush_yards=100, rush_tds=1, receptions=4, rec_yards=40, rec_tds=0.5) for _ in range(11)]
    assert calibrate_production_pace(row, player=player, games=games)
    assert 24 < row.fantasy_points < 28
    assert row.rush_yards > 90 and row.rec_yards > 35
    assert row.rush_attempts == pytest.approx((2 * prior_carries + 11 * 15) / 13)


@pytest.mark.parametrize('status', ['OUT','OUT_FOR_SEASON','IR'])
def test_production_cannot_revive_unavailable_players(status):
    player, row = candidate(injury=Injury(status=status))
    before = row.fantasy_points
    assert not calibrate_production_pace(row, player=player, games=[dict(receptions=8,rec_yards=100)]*11)
    assert before == row.fantasy_points == 0


def test_health_and_matchup_apply_once_to_the_observed_production():
    games=[dict(receptions=6, rec_yards=75, rec_tds=0.5)]*10
    player, healthy=candidate()
    _, limited=candidate(injury=Injury(status='QUESTIONABLE'))
    calibrate_production_pace(healthy,player=player,games=games)
    calibrate_production_pace(limited,player=player,games=games)
    assert limited.fantasy_points == pytest.approx(healthy.fantasy_points*0.7,abs=0.02)
    _, difficult=candidate()
    defense=DefenseRating(pass_yards_multiplier=0.9,pass_catch_multiplier=0.94,pass_td_multiplier=0.85,
        rush_yards_multiplier=0.9,rush_td_multiplier=0.85)
    calibrate_production_pace(difficult,player=player,games=games,defense=defense)
    assert difficult.fantasy_points < healthy.fantasy_points


def test_sparse_history_and_locked_forecasts_are_preserved():
    player,row=candidate();before=row.fantasy_points
    assert not calibrate_production_pace(row,player=player,games=[dict(receptions=12,rec_yards=200)]*2)
    assert row.fantasy_points==before
    row.locked_at=datetime.now(timezone.utc)
    assert not calibrate_production_pace(row,player=player,games=[dict(receptions=12,rec_yards=200)]*10)
    assert row.fantasy_points==before


def test_fpts_only_and_incomplete_rows_are_not_component_production():
    player,row=candidate();before=row.fantasy_points
    assert not calibrate_production_pace(row,player=player,games=[dict(fpts=40)]*11)
    assert not calibrate_production_pace(row,player=player,games=[dict(receptions=10,_scoring_incomplete=True)]*11)
    assert row.fantasy_points==before


def test_te_starter_has_a_role_prior_instead_of_equal_room_split():
    starter=Player(id=1,name='Starter',position='TE',school='Cincinnati',depth_order=1)
    reserve=Player(id=2,name='Reserve',position='TE',school='Cincinnati',depth_order=2)
    usage={row.player_id:row for row in compute_usage_shares([reserve,starter],{},2026,13)}
    assert usage[starter.id].target_share==pytest.approx(0.12)
    assert usage[reserve.id].target_share==pytest.approx(0.04)


def test_low_production_backup_is_not_given_a_blanket_starter_boost():
    player,row=candidate();before=row.fantasy_points
    calibrate_production_pace(row,player=player,games=[dict(receptions=0,rec_yards=0,rec_tds=0)]*10)
    assert row.fantasy_points<before


def test_only_prior_final_game_facts_can_calibrate_a_published_role_forecast(db_session):
    from collegefootballfantasy_api.app.models.game import Game
    from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
    from collegefootballfantasy_api.app.models.player_stat import PlayerStat
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    from collegefootballfantasy_api.app.services.official_role_corrections import publish_role_corrected_week
    from collegefootballfantasy_api.app.crud.projection import get_projection

    player=Player(name='Established TE',school='Cincinnati',position='TE',depth_order=1)
    db_session.add(player);db_session.flush()
    for week in range(1,6):
        game=Game(external_id=str(9000+week),season=2026,week=week,season_type='regular',
            schedule_status='final' if week<=3 else 'in',home_team='Cincinnati',away_team='Houston',
            start_date=datetime(2026,9,week,tzinfo=timezone.utc))
        db_session.add(game);db_session.flush()
        db_session.add(TeamSchedule(team_name='Cincinnati',season=2026,week=week,
            game_id=game.id,opponent_name='Houston',location='home',is_bye=False))
        db_session.add(PlayerGameStat(player_id=player.id,game_id=game.id,season=2026,week=week,
            source='espn_final_boxscore',stats=dict(receptions=6,rec_yards=75,rec_tds=1) if week<=3
                else dict(receptions=50,rec_yards=900,rec_tds=8)))
    # A weekly/live aggregate is never an accepted final-game baseline.
    db_session.add(PlayerStat(player_id=player.id,season=2026,week=4,verified=True,source='espn',
        stats=dict(receptions=50,rec_yards=900,rec_tds=8)))
    db_session.add(WeeklyProjection(player_id=player.id,season=2026,week=5,
        projection_version='MIDWEEK',is_published=True,fantasy_points=3))
    db_session.commit()
    for _ in range(2):
        publish_role_corrected_week(db_session,players=[player],season=2026,week=5,
            source_url='https://example.com/verified-role')
        db_session.commit()
        row=get_projection(db_session,player.id,2026,5)
        assert row.baseline_games_played==3
        assert row.model_version=='verified_production_pace_v1'
        assert 11<row.fantasy_points<20
        assert row.fantasy_points==calculate_fantasy_points(
            {key:getattr(row,key) for key in ['receptions','rec_yards','rec_tds','rush_yards','rush_tds']},position='TE')
    assert db_session.query(WeeklyProjection).filter_by(player_id=player.id,projection_version='CORRECTED_ROLE').count()==1
