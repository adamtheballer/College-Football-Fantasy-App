"""Finality, full-pool publication, temporal history and correction regressions."""
from unittest.mock import patch
import pytest
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartWeek, PlayerChartPublicationRun
from collegefootballfantasy_api.app.services.player_chart_publication import publish_finalized_chart_week
from collegefootballfantasy_api.app.services.player_trajectory import build_player_trajectory
from collegefootballfantasy_api.app.services.player_trade_value import calculate_weekly_trade_values, calculate_player_trade_value, get_player_trade_values, weekly_value_weights
from tests.api.scoring_helpers import create_scoring_fixture


def final_week(db, week=1):
    league, home, away, players, matchup = create_scoring_fixture(db)
    matchup.week, matchup.status = week, "final"
    db.flush()
    return matchup


def test_week_transition_retains_actuals_and_one_upcoming_forecast(db_session, monkeypatch):
    from collegefootballfantasy_api.app.services import player_trajectory as trajectory_service
    monkeypatch.setattr(trajectory_service, "calendar_matchup_display_week", lambda _season: 7)
    weeks = [final_week(db_session, w) for w in range(1, 7)]
    p = Player(name="Transition WR", school="Illinois", position="WR", raw_cfb27_rating=84)
    db_session.add(p); db_session.flush()
    db_session.add(PlayerStat(player_id=p.id, season=2026, week=6, stats={"fantasy_points":18.4}, verified=True))
    for week, points in [(6,20),(7,21.2),(8,25)]:
        db_session.add(WeeklyProjection(player_id=p.id, season=2026, week=week, fantasy_points=points, is_published=True))
    db_session.flush()
    result = publish_finalized_chart_week(db_session, season=2026, week=6, batch_size=2)
    assert result["actuals"] == 1
    trajectory = build_player_trajectory(db_session, player_id=p.id, season=2026)
    assert [(pt.week,pt.actual_points) for pt in trajectory.projection if pt.actual_points is not None] == [(6,18.4)]
    assert [pt.week for pt in trajectory.projection if not pt.is_finalized] == [7]
    db_session.add(PlayerStat(player_id=p.id, season=2026, week=7, stats={"fantasy_points":24.6}, verified=True))
    final_week(db_session, 7)
    publish_finalized_chart_week(db_session, season=2026, week=7)
    monkeypatch.setattr(trajectory_service, "calendar_matchup_display_week", lambda _season: 8)
    trajectory = build_player_trajectory(db_session, player_id=p.id, season=2026)
    assert [(pt.week,pt.actual_points) for pt in trajectory.projection if pt.actual_points is not None] == [(6,18.4),(7,24.6)]
    assert [pt.week for pt in trajectory.projection if not pt.is_finalized] == [8]
    weeks[5].status = "live"  # later administrative changes cannot erase snapshots
    db_session.flush()
    assert db_session.query(PlayerChartWeek).filter_by(player_id=p.id, season=2026).count() == 2


def test_full_catalog_keyset_batches_unrostered_positions_zero_negative_and_failures(db_session):
    from datetime import datetime,timedelta,timezone
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartForecast
    kickoff=datetime(2026,9,5,18,tzinfo=timezone.utc)
    matchup = final_week(db_session)
    players = [Player(name=f"Catalog {i}", school="Texas", position=["QB","RB","WR","TE","K"][i%5]) for i in range(815)]
    db_session.add_all(players); db_session.flush()
    db_session.add(TeamSchedule(team_name="Texas",season=2026,week=1,location="home",kickoff_at=kickoff))
    for i,p in enumerate(players):
        db_session.add(PlayerStat(player_id=p.id, season=2026, week=1, verified=True, stats={"fantasy_points": -2 if i==0 else 0 if i==1 else 10}))
        db_session.add(WeeklyProjection(player_id=p.id,season=2026,week=1,fantasy_points=9.2,updated_at=kickoff-timedelta(hours=1)))
    db_session.flush()
    matchup.status = "live"
    assert publish_finalized_chart_week(db_session, season=2026, week=1)["status"] == "waiting_for_finality"
    assert db_session.query(PlayerChartWeek).count() == 0
    matchup.status = "final"
    result = publish_finalized_chart_week(db_session, season=2026, week=1, batch_size=19)
    assert result["actuals"] == 815
    assert db_session.query(PlayerChartForecast).count()==815
    assert db_session.query(PlayerChartWeek).filter_by(player_id=players[0].id).one().standard_points == -2
    assert db_session.query(PlayerChartWeek).filter_by(player_id=players[1].id).one().standard_points == 0
    repeat = publish_finalized_chart_week(db_session, season=2026, week=1, batch_size=19)
    assert repeat["unchanged"] == 815
    assert db_session.query(PlayerChartWeek).count() == 815
    values = calculate_weekly_trade_values(db_session,season=2026,week=1)
    assert values["eligible"] == values["calculated"] == 815
    assert values["status"] == "complete"
    stat = db_session.query(PlayerStat).filter_by(player_id=players[0].id).one()
    stat.stats = {"fantasy_points": 12}
    matchup.status = "stat_corrected"
    publish_finalized_chart_week(db_session, season=2026, week=1)
    assert db_session.query(PlayerChartWeek).filter_by(player_id=players[0].id).one().standard_points == 12
    assert db_session.query(PlayerChartWeek).count() == 815


def test_missing_unverified_and_unrecognized_stats_never_become_zero(db_session):
    final_week(db_session)
    players = [Player(name=f"Missing {i}", school="Texas", position="WR") for i in range(4)]
    db_session.add_all(players); db_session.flush()
    db_session.add_all([PlayerStat(player_id=players[0].id, season=2026, week=1, verified=False, stats={"rec_yards":100}),PlayerStat(player_id=players[1].id, season=2026, week=1, verified=True, stats={"metadata":1}),PlayerStat(player_id=players[2].id, season=2026, week=1, verified=True, stats={"rec_yards":0})])
    db_session.flush()
    result=publish_finalized_chart_week(db_session,season=2026,week=1)
    assert result["status"] == "partial" and result["actuals"] == 1
    assert all(p.id in result["missing_stats"] for p in [players[0],players[1],players[3]])
    assert db_session.query(PlayerChartPublicationRun).one().coverage_json["missing_stats"] == result["missing_stats"]


def test_failed_player_does_not_abort_unaffected_players(db_session):
    final_week(db_session)
    players=[Player(name=f"Resilient {i}",school="Texas",position="WR",raw_cfb27_rating=80) for i in range(3)]
    db_session.add_all(players); db_session.flush()
    original=calculate_player_trade_value
    def isolated_failure(db, **kwargs):
        if kwargs["player_id"] == players[1].id:
            raise RuntimeError("isolated calculation failure")
        return original(db, **kwargs)
    with patch("collegefootballfantasy_api.app.services.player_trade_value.calculate_player_trade_value",side_effect=isolated_failure):
        result=calculate_weekly_trade_values(db_session,season=2026,week=1)
    assert result["calculated"] == 2 and result["status"] == "partial"
    assert result["failures"][0]["player_id"] == players[1].id


def test_history_uses_each_rows_value_and_old_recalculation_cannot_regress_current(db_session):
    final_week(db_session)
    p=Player(name="Historical Value",school="Texas",position="WR",raw_cfb27_rating=80)
    db_session.add_all([p,Player(name="Peer Value",school="Texas",position="WR",raw_cfb27_rating=95)]);db_session.flush()
    first=calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=1)
    value1=first.value
    final_week(db_session,2)
    db_session.add(PlayerStat(player_id=p.id,season=2026,week=2,stats={"fantasy_points":40},verified=True));db_session.flush()
    second=calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=2)
    value2=second.value
    assert value1 != value2
    p.raw_cfb27_rating=99
    db_session.flush()
    recalculated=calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=1)
    assert recalculated.value == value1
    assert p.value_calculation_week == 2 and p.current_value_rating == value2
    history=get_player_trade_values(db_session,player_id=p.id,season=2026).history
    assert [(r.week,r.value) for r in history] == [(1,value1),(2,value2)]
    assert weekly_value_weights(11) != weekly_value_weights(12)
    assert weekly_value_weights(12) == weekly_value_weights(13) == (0.10,0.75,0.15)
    late=Player(name="No Historical Inputs",school="Texas",position="WR",raw_cfb27_rating=90)
    db_session.add(late);db_session.flush()
    with pytest.raises(ValueError,match="historical value inputs unavailable"):
        calculate_player_trade_value(db_session,player_id=late.id,season=2026,week=1)


def test_rescores_unrostered_receiver_for_selected_league_without_mutating_scores(db_session):
    from collegefootballfantasy_api.app.models.league import League
    from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
    from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
    final_week(db_session)
    p=Player(name="Custom Receiving",school="Illinois",position="WR")
    league=League(name="Custom Points",season_year=2026)
    db_session.add_all([p,league]);db_session.flush()
    db_session.add_all([LeagueSettings(league_id=league.id,scoring_json={"receptions":2,"rec_yards":0.2,"rec_tds":6}),PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"receptions":5,"rec_yards":71,"rec_tds":2})]);db_session.flush()
    publish_finalized_chart_week(db_session,season=2026,week=1)
    trajectory=build_player_trajectory(db_session,player_id=p.id,season=2026,league_id=league.id)
    assert trajectory.projection[0].actual_points == 36.2
    assert db_session.query(PlayerWeekScore).filter_by(player_id=p.id).count() == 0


def test_last_week_publication_runs_without_next_week_schedule(db_session):
    from collegefootballfantasy_api.app.services.weekly_outlook_refresh import refresh_post_final_outlook
    final_week(db_session,1)
    final_week(db_session,13)
    p=Player(name="Last Week Kicker",school="Texas",position="K",raw_cfb27_rating=80)
    db_session.add(p);db_session.flush()
    db_session.add(PlayerStat(player_id=p.id,season=2026,week=13,verified=True,stats={"xp_made":0,"fg_missed":1}));db_session.flush()
    refresh_post_final_outlook(db_session,season=2026,completed_week=13)
    assert db_session.query(PlayerChartWeek).filter_by(player_id=p.id,week=13).one().standard_points <= 0
    assert get_player_trade_values(db_session,player_id=p.id,season=2026).history[0].week == 13


def test_original_forecast_is_proven_pregame_and_frozen_through_corrections(db_session):
    from datetime import datetime,timedelta,timezone
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    final_week(db_session)
    kickoff=datetime(2026,9,5,18,tzinfo=timezone.utc)
    p=Player(name="Frozen Forecast",school="TEXAS",position="RB")
    db_session.add(p);db_session.flush()
    db_session.add(TeamSchedule(team_name="Texas",season=2026,week=1,location="home",kickoff_at=kickoff))
    original=WeeklyProjection(player_id=p.id,season=2026,week=1,fantasy_points=14,projection_version="FINAL",rush_yards=80,rush_tds=1,updated_at=kickoff-timedelta(hours=2))
    late=WeeklyProjection(player_id=p.id,season=2026,week=1,fantasy_points=40,projection_version="CORRECTED_LATE",updated_at=kickoff+timedelta(hours=5))
    stat=PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"rush_yards":100})
    db_session.add_all([original,late,stat]);db_session.flush()
    publish_finalized_chart_week(db_session,season=2026,week=1)
    point=build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0]
    assert (point.points,point.actual_points,point.projection_version)==(14,10,"FINAL")
    original.fantasy_points=99
    stat.stats={"rush_yards":110}
    db_session.flush()
    publish_finalized_chart_week(db_session,season=2026,week=1)
    point=build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0]
    assert (point.points,point.actual_points)==(14,11)
    assert db_session.query(PlayerChartPublicationRun).order_by(PlayerChartPublicationRun.id.desc()).first().coverage_json["corrections"][0]["prior_points"]==10


def test_late_forecast_and_partial_stats_remain_unavailable_until_supported_retry(db_session):
    from datetime import datetime,timezone
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    final_week(db_session)
    p=Player(name="Delayed Stats",school="Illinois",position="WR")
    db_session.add(p);db_session.flush()
    stat=PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"receptions":3,"rec_yards":40,"_scoring_incomplete":True})
    db_session.add_all([stat,TeamSchedule(team_name="Illinois",season=2026,week=1,location="home",kickoff_at=datetime(2026,9,5,tzinfo=timezone.utc)),WeeklyProjection(player_id=p.id,season=2026,week=1,fantasy_points=99)])
    db_session.flush()
    result=publish_finalized_chart_week(db_session,season=2026,week=1)
    assert p.id in result["missing_stats"] and result["status"]=="partial"
    assert build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0].source=="unavailable"
    stat.stats={"receptions":3,"rec_yards":40};db_session.flush()
    publish_finalized_chart_week(db_session,season=2026,week=1)
    point=build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0]
    assert point.actual_points==7 and point.points is None and point.projection_version is None


def test_week_zero_opener_matches_matchup_scoring_without_double_counting(db_session):
    from datetime import datetime,timezone
    from collegefootballfantasy_api.app.models.game import Game
    from collegefootballfantasy_api.app.services.scoring_service import _stat_map
    final_week(db_session)
    p=Player(name="Opening QB",school="Texas",position="QB",raw_cfb27_rating=90)
    db_session.add(p);db_session.flush()
    db_session.add(Game(season=2026,week=0,home_team="Texas",away_team="Ohio State",external_id="opening-provider",start_date=datetime(2026,8,29,18,tzinfo=timezone.utc),schedule_status="final",season_type="regular"))
    opener=PlayerStat(player_id=p.id,season=2026,week=0,verified=True,stats={"fantasy_points":18.4})
    db_session.add_all([opener,PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"fantasy_points":99})]);db_session.flush()
    assert _stat_map(db_session,2026,1,{p.id})[p.id].week==0
    publish_finalized_chart_week(db_session,season=2026,week=1)
    snapshot=db_session.query(PlayerChartWeek).filter_by(player_id=p.id).one()
    assert snapshot.week==1 and snapshot.source_stat_id==opener.id and snapshot.standard_points==18.4
    assert build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0].actual_points==18.4
    from collegefootballfantasy_api.app.services.player_trade_value import _value_stat_inputs
    assert _value_stat_inputs(db_session,season=2026,week=1)[p.id][0]["fantasy_points"]==18.4
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    from collegefootballfantasy_api.app.services.weekly_outlook_refresh import refresh_post_final_outlook
    db_session.add(TeamSchedule(team_name="Texas",season=2026,week=2,opponent_name="Illinois",location="home"));db_session.flush()
    with patch("collegefootballfantasy_api.app.services.weekly_outlook_refresh.build_weekly_projections",return_value=[]) as model:
        refresh_post_final_outlook(db_session,season=2026,completed_week=1)
    assert model.call_args.kwargs["player_stats"][p.id]["fantasy_points"]==18.4


def test_value_history_requires_finality_proof_and_survives_later_admin_changes(db_session):
    from datetime import datetime,timezone
    from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
    p=Player(name="Value Proof",school="Texas",position="WR",raw_cfb27_rating=84)
    db_session.add(p);db_session.flush()
    db_session.add(PlayerTradeValue(player_id=p.id,season=2026,week=1,policy_version="universal_v2",value=95,tier="test",confidence=1,calculated_at=datetime.now(timezone.utc),input_version="legacy",input_context_json={"some_context":True}))
    db_session.flush()
    assert not get_player_trade_values(db_session,player_id=p.id,season=2026).history
    assert [point.week for point in build_player_trajectory(db_session,player_id=p.id,season=2026).value]==[0]
    matchup=final_week(db_session)
    calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=1)
    publish_finalized_chart_week(db_session,season=2026,week=1)
    matchup.status="projected";db_session.flush()
    assert get_player_trade_values(db_session,player_id=p.id,season=2026).history[-1].week==1
    assert build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0].is_finalized


def test_value_stat_inputs_exclude_unfinished_weeks_and_future_seasons(db_session):
    from collegefootballfantasy_api.app.services.player_trade_value import _value_stat_inputs
    final_week(db_session,1);future=final_week(db_session,2);future.status="live"
    p=Player(name="Cutoff Stats",school="Texas",position="WR",raw_cfb27_rating=80)
    db_session.add(p);db_session.flush()
    db_session.add_all([PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"rec_yards":0}),PlayerStat(player_id=p.id,season=2026,week=2,verified=True,stats={"rec_yards":999}),PlayerStat(player_id=p.id,season=2025,week=1,verified=True,stats={"rec_yards":500})]);db_session.flush()
    assert _value_stat_inputs(db_session,season=2026,week=2)[p.id]==[{"rec_yards":0}]
    assert get_player_trade_values(db_session,player_id=p.id,season=2025).current is None
    assert build_player_trajectory(db_session,player_id=p.id,season=2025).value==[]


def test_no_hindsight_backfill_when_later_final_week_exists_across_a_gap(db_session):
    final_week(db_session,1);final_week(db_session,6)
    p=Player(name="No Hindsight",school="Texas",position="WR",raw_cfb27_rating=90)
    db_session.add(p);db_session.flush()
    with pytest.raises(ValueError,match="historical value inputs unavailable"):
        calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=1)


def test_week_six_value_follows_existing_factor_formula_and_frozen_peer_positions(db_session):
    for week in range(1,7): final_week(db_session,week)
    p=Player(name="Formula Receiver",school="Texas",position="WR",raw_cfb27_rating=80)
    peer=Player(name="Formula Peer",school="Texas",position="WR",raw_cfb27_rating=95)
    db_session.add_all([p,peer]);db_session.flush()
    for player,actual,forecast in [(p,10,20),(peer,20,10)]:
        db_session.add_all([PlayerStat(player_id=player.id,season=2026,week=6,verified=True,stats={"fantasy_points":actual}),WeeklyProjection(player_id=player.id,season=2026,week=6,fantasy_points=forecast)])
    db_session.flush()
    row=calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=6)
    assert row.factor_breakdown_json=={"preseasonRating":15,"seasonPerformance":19.25,"recentForm":8.25,"futureProjection":9.75,"usageRole":3,"availability":1.5,"positionalScarcity":.41}
    assert row.value==57.2
    peer.position="RB";p.raw_cfb27_rating=99;db_session.flush()
    assert calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=6).value==57.2


@pytest.mark.parametrize("stats",[{"rec_yards":10,"receptions":None},{"rec_yards":10,"rec_tds":float("nan")},{"fantasy_points":0,"_scoring_incomplete":True}])
def test_unknown_scoring_fields_do_not_become_confirmed_zeros(stats):
    from collegefootballfantasy_api.app.services.player_chart_publication import points_from_verified_stats
    assert points_from_verified_stats(stats,position="WR") is None


def test_backfill_cli_audits_then_repairs_locally_without_duplicates(db_session,monkeypatch,capsys):
    import json
    import sys
    import scripts.backfill_player_charts as backfill
    final_week(db_session)
    players=[Player(name=f"Backfill {position}",school="Texas",position=position,raw_cfb27_rating=80) for position in ["QB","RB","WR","TE","K"]]
    db_session.add_all(players);db_session.flush()
    for p in players:
        db_session.add(PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"fantasy_points":0}))
    db_session.commit()
    monkeypatch.setattr(backfill,"create_engine",lambda *args,**kwargs:db_session.bind)
    argv=["backfill_player_charts.py","--database-url","sqlite://","--season","2026","--weeks","1"]
    monkeypatch.setattr(sys,"argv",argv)
    backfill.main();audit=json.loads(capsys.readouterr().out)
    assert audit["weeks"][0]["actual_snapshots_before"]==audit["weeks"][0]["actual_snapshots_after"]==0
    assert audit["weeks"][0]["supported_source_actuals"]==5
    monkeypatch.setattr(sys,"argv",argv+["--apply-local"])
    backfill.main();repaired=json.loads(capsys.readouterr().out)
    assert repaired["weeks"][0]["actual_snapshots_after"]==repaired["weeks"][0]["value_snapshots_after"]==5
    backfill.main();repeat=json.loads(capsys.readouterr().out)
    assert repeat["weeks"][0]["actual_publication"]["unchanged"]==5
    assert repeat["weeks"][0]["actual_snapshots_after"]==5


def test_corrections_retain_recorded_scoring_rules(db_session):
    final_week(db_session)
    p=Player(name="Recorded Rules",school="Texas",position="WR")
    db_session.add(p);db_session.flush()
    stat=PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"rec_yards":100})
    db_session.add(stat);db_session.flush()
    publish_finalized_chart_week(db_session,season=2026,week=1)
    stat.stats={"rec_yards":110};db_session.flush()
    with patch("collegefootballfantasy_api.app.services.player_chart_publication.get_scoring_rules",return_value={"rec_yards":.2}):
        publish_finalized_chart_week(db_session,season=2026,week=1)
    assert db_session.query(PlayerChartWeek).filter_by(player_id=p.id).one().standard_points==11


def test_worker_capture_freezes_unfinished_forecast_without_view_or_roster(db_session):
    from datetime import datetime,timedelta,timezone
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartForecast
    from collegefootballfantasy_api.app.services.chart_forecasts import capture_started_chart_forecasts
    kickoff=datetime(2026,9,5,18,tzinfo=timezone.utc)
    p=Player(name="Unviewed Forecast",school="Texas",position="RB")
    db_session.add(p);db_session.flush()
    source=WeeklyProjection(player_id=p.id,season=2026,week=1,fantasy_points=14,rush_yards=80,rush_tds=1,updated_at=kickoff-timedelta(hours=1))
    db_session.add_all([source,TeamSchedule(team_name="Texas",season=2026,week=1,location="home",kickoff_at=kickoff)]);db_session.flush()
    assert capture_started_chart_forecasts(db_session,season=2026,week=1,now=kickoff-timedelta(minutes=1))["captured"]==0
    assert capture_started_chart_forecasts(db_session,season=2026,week=1,now=kickoff)["captured"]==1
    source.fantasy_points=99;source.rush_yards=999;db_session.flush()
    assert capture_started_chart_forecasts(db_session,season=2026,week=1,now=kickoff+timedelta(hours=3))["unchanged"]==1
    assert db_session.query(PlayerChartForecast).filter_by(player_id=p.id).count()==1
    point=build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0]
    assert point.points==14 and point.actual_points is None and not point.is_finalized
    assert db_session.query(PlayerChartWeek).count()==0


def test_late_recovered_original_forecast_enriches_without_changing_actual(db_session):
    from datetime import datetime,timedelta,timezone
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    final_week(db_session)
    kickoff=datetime(2026,9,5,18,tzinfo=timezone.utc)
    p=Player(name="Recovered Original",school="Texas",position="WR")
    db_session.add(p);db_session.flush()
    db_session.add_all([TeamSchedule(team_name="Texas",season=2026,week=1,location="home",kickoff_at=kickoff),PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"rec_yards":100})]);db_session.flush()
    publish_finalized_chart_week(db_session,season=2026,week=1)
    assert build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0].points is None
    db_session.add(WeeklyProjection(player_id=p.id,season=2026,week=1,fantasy_points=14,updated_at=kickoff-timedelta(hours=1)));db_session.flush()
    result=publish_finalized_chart_week(db_session,season=2026,week=1)
    assert result["forecast_recoveries"]==[p.id]
    point=build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0]
    assert (point.points,point.actual_points)==(14,10)
    assert db_session.query(PlayerChartWeek).filter_by(player_id=p.id).count()==1


def test_bye_unknown_postponed_and_confirmed_nonparticipation_stay_distinct(db_session):
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    from collegefootballfantasy_api.app.models.injury import Injury
    final_week(db_session)
    bye=Player(name="Bye Player",school="Texas",position="TE")
    unknown=Player(name="Postponed Unknown",school="Illinois",position="RB")
    out=Player(name="Confirmed No Participation",school="Ohio State",position="WR")
    db_session.add_all([bye,unknown,out]);db_session.flush()
    db_session.add_all([TeamSchedule(team_name="Texas",season=2026,week=1,location="bye",is_bye=True),PlayerStat(player_id=out.id,season=2026,week=1,verified=True,stats={"receptions":0,"rec_yards":0,"rec_tds":0}),Injury(player_id=out.id,season=2026,week=1,status="OUT")]);db_session.flush()
    publish_finalized_chart_week(db_session,season=2026,week=1)
    assert build_player_trajectory(db_session,player_id=bye.id,season=2026).projection[0].source=="bye"
    assert build_player_trajectory(db_session,player_id=unknown.id,season=2026).projection[0].source=="unavailable"
    assert build_player_trajectory(db_session,player_id=out.id,season=2026).projection[0].actual_points==0
    assert db_session.query(PlayerChartWeek).filter_by(player_id=unknown.id).count()==0


def test_flat_values_record_a_real_recomputation_after_changed_inputs(db_session):
    final_week(db_session)
    players=[Player(name=f"Flat Recompute {i}",school="Texas",position="WR",raw_cfb27_rating=80+i) for i in range(2)]
    db_session.add_all(players);db_session.flush()
    stat=PlayerStat(player_id=players[0].id,season=2026,week=1,verified=True,stats={"rec_yards":100})
    db_session.add(stat);db_session.flush()
    calculate_weekly_trade_values(db_session,season=2026,week=1)
    stat.stats={"rec_yards":100,"source_revision":2};db_session.flush()
    result=calculate_weekly_trade_values(db_session,season=2026,week=1)
    assert result["recomputed_unchanged"]==2 and result["changes"]==[]
    assert result["calculated"]==2 and not result.get("unchanged")


def test_delayed_prior_week_does_not_move_the_upcoming_forecast_backwards(db_session):
    final_week(db_session,1)
    late=final_week(db_session,2);late.status="live"
    final_week(db_session,3)
    p=Player(name="Delayed Calendar",school="Texas",position="WR")
    db_session.add(p);db_session.flush()
    for week in [2,4]: db_session.add(WeeklyProjection(player_id=p.id,season=2026,week=week,fantasy_points=20))
    db_session.flush()
    points=build_player_trajectory(db_session,player_id=p.id,season=2026).projection
    assert [point.week for point in points if point.source=="published" and not point.is_finalized]==[4]
    pending=next(point for point in points if point.week==2)
    assert pending.source=="unavailable" and pending.actual_points is None
    assert pending.projection_status=="AWAITING_WEEK_FINALITY" and not pending.is_finalized


def test_preseason_chart_and_card_share_existing_official_availability_adjustment(db_session):
    from collegefootballfantasy_api.app.models.injury import Injury
    from collegefootballfantasy_api.app.services.player_trade_value import current_trade_value_snapshot
    p=Player(name="Availability Baseline",school="Missouri",position="RB",raw_cfb27_rating=96)
    db_session.add(p);db_session.flush()
    db_session.add(Injury(player_id=p.id,season=2026,week=1,status="OUT",return_timeline="2-4 weeks"));db_session.flush()
    chart=build_player_trajectory(db_session,player_id=p.id,season=2026)
    assert chart.value[0].value==current_trade_value_snapshot(db_session,player_id=p.id,season=2026)["value"]==67.2


def test_reviewed_full_and_season_out_use_existing_availability_categories(db_session):
    from collegefootballfantasy_api.app.models.injury import Injury
    final_week(db_session)
    for status,expected_factor in [("FULL",1.0),("OUT_FOR_SEASON",.3)]:
        p=Player(name=f"Reviewed {status}",school="Texas",position="WR",raw_cfb27_rating=84)
        db_session.add(p);db_session.flush()
        db_session.add(Injury(player_id=p.id,season=2026,week=1,status=status));db_session.flush()
        row=calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=1)
        assert row.factor_breakdown_json["availability"]==expected_factor


def test_current_season_initialization_replaces_a_proven_prior_season_cache(db_session):
    p=Player(name="Season Rollover Value",school="Texas",position="WR",raw_cfb27_rating=90,current_value_rating=55,value_calculation_week=13,value_input_json={"season":2025})
    db_session.add(p);db_session.flush()
    before=get_player_trade_values(db_session,player_id=p.id,season=2026)
    assert before.current.week==0 and before.current.value==90
    calculate_player_trade_value(db_session,player_id=p.id,season=2026,week=0)
    assert p.current_value_rating==90 and p.value_calculation_week==0 and p.value_input_json["season"]==2026


@pytest.mark.parametrize("in_season",[False,True])
def test_past_season_missing_value_context_never_uses_current_catalog(db_session,in_season):
    if in_season:
        match=final_week(db_session);match.season=2025
    p=Player(name="Past Season Unavailable",school="Texas",position="WR",raw_cfb27_rating=90,current_value_rating=90,value_input_json={"season":2026},value_calculation_week=0)
    db_session.add(p);db_session.flush()
    with pytest.raises(ValueError,match="historical .*inputs unavailable"):
        calculate_player_trade_value(db_session,player_id=p.id,season=2025,week=1)
    assert p.current_value_rating==90


def test_unrostered_late_game_delays_whole_week_chart_publication(db_session):
    from collegefootballfantasy_api.app.models.game import Game
    from collegefootballfantasy_api.app.services.fantasy_week_finality import week_is_authoritatively_finalized
    final_week(db_session)
    p=Player(name="Late Unrostered WR",school="Texas",position="WR",raw_cfb27_rating=84)
    db_session.add(p);db_session.flush()
    game=Game(season=2026,week=1,home_team="Texas",away_team="Illinois",external_id="late-catalog-game",season_type="regular",schedule_status="in")
    db_session.add_all([game,PlayerStat(player_id=p.id,season=2026,week=1,verified=True,stats={"rec_yards":100})]);db_session.flush()
    assert not week_is_authoritatively_finalized(db_session,season=2026,week=1)
    assert publish_finalized_chart_week(db_session,season=2026,week=1)["status"]=="waiting_for_finality"
    point=build_player_trajectory(db_session,player_id=p.id,season=2026)
    assert not any(p.actual_points is not None for p in point.projection)
    game.schedule_status="final";db_session.flush()
    assert publish_finalized_chart_week(db_session,season=2026,week=1)["actuals"]==1


def test_final_game_fact_backfill_without_weekly_record_preserves_league_results(db_session):
    from collegefootballfantasy_api.app.models.game import Game
    from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
    from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
    final_week(db_session)
    p=Player(name="Final Game Recovery",school="Texas",position="WR",raw_cfb27_rating=84)
    game=Game(season=2026,week=1,home_team="Texas",away_team="Illinois",external_id="verified-final-event",season_type="regular",schedule_status="final")
    db_session.add_all([p,game]);db_session.flush()
    fact=PlayerGameStat(player_id=p.id,game_id=game.id,season=2026,week=1,source="espn_final_boxscore",stats={"receptions":5,"rec_yards":71,"rec_tds":2})
    db_session.add(fact);db_session.flush()
    prior_weekly=db_session.query(PlayerStat).count()
    prior_scores=db_session.query(PlayerWeekScore).count()
    publish_finalized_chart_week(db_session,season=2026,week=1)
    snapshot=db_session.query(PlayerChartWeek).filter_by(player_id=p.id).one()
    assert snapshot.standard_points==24.1 and snapshot.source_stat_id is None
    assert snapshot.stats_json["_chart_game_stat_id"]==fact.id
    fact.stats={"receptions":5,"rec_yards":81,"rec_tds":2};db_session.flush()
    corrected=publish_finalized_chart_week(db_session,season=2026,week=1)
    assert corrected["corrections"][0]["prior_points"]==24.1
    assert snapshot.standard_points==25.1
    assert db_session.query(PlayerStat).count()==prior_weekly
    assert db_session.query(PlayerWeekScore).count()==prior_scores
    assert calculate_weekly_trade_values(db_session,season=2026,week=1)["calculated"]==1


def test_live_game_facts_do_not_fill_a_final_history_gap(db_session):
    from collegefootballfantasy_api.app.models.game import Game
    from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
    final_week(db_session)
    p=Player(name="Live Fact Rejected",school="Texas",position="WR")
    game=Game(season=2026,week=1,home_team="Texas",away_team="Illinois",external_id="live-source-final-game",season_type="regular",schedule_status="final")
    db_session.add_all([p,game]);db_session.flush()
    db_session.add(PlayerGameStat(player_id=p.id,game_id=game.id,season=2026,week=1,source="espn_live_boxscore",stats={"rec_yards":100}));db_session.flush()
    result=publish_finalized_chart_week(db_session,season=2026,week=1)
    assert p.id in result["missing_stats"]
    assert db_session.query(PlayerChartWeek).filter_by(player_id=p.id).count()==0


def test_postponement_does_not_freeze_an_expired_pregame_forecast(db_session):
    from datetime import datetime,timedelta,timezone
    from collegefootballfantasy_api.app.models.game import Game
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    from collegefootballfantasy_api.app.services.chart_forecasts import capture_started_chart_forecasts
    kickoff=datetime(2026,9,5,18,tzinfo=timezone.utc)
    p=Player(name="Rescheduled Forecast",school="Texas",position="WR")
    game=Game(season=2026,week=1,home_team="Texas",away_team="Illinois",external_id="rescheduled-event",season_type="regular",schedule_status="postponed")
    db_session.add_all([p,game]);db_session.flush()
    schedule=TeamSchedule(team_name="Texas",season=2026,week=1,location="home",game_id=game.id,kickoff_at=kickoff)
    forecast=WeeklyProjection(player_id=p.id,season=2026,week=1,fantasy_points=14,updated_at=kickoff-timedelta(hours=1))
    db_session.add_all([schedule,forecast]);db_session.flush()
    blocked=capture_started_chart_forecasts(db_session,season=2026,week=1,now=kickoff+timedelta(days=1))
    assert blocked["captured"]==0 and blocked["blocked_game_ids"]==[p.id]
    schedule.kickoff_at=kickoff+timedelta(days=7);game.schedule_status="in"
    forecast.fantasy_points=21.2;forecast.updated_at=kickoff+timedelta(days=6);db_session.flush()
    assert capture_started_chart_forecasts(db_session,season=2026,week=1,now=schedule.kickoff_at)["captured"]==1
    assert build_player_trajectory(db_session,player_id=p.id,season=2026).projection[0].points==21.2
