from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services import early_game_schedule_reconciliation as reconciliation
from collegefootballfantasy_api.app.services.player_game_display import player_game_display_state
from collegefootballfantasy_api.app.services.player_game_log import build_player_game_log
from collegefootballfantasy_api.app.services.season_calendar import SealedScheduleRow, SealedScheduleSnapshot


def _snapshot() -> SealedScheduleSnapshot:
    return SealedScheduleSnapshot(
        season=2026,
        source_identity="test",
        source_revision="test",
        source_sha256="test",
        format_version="SEALED_CFB_SCHEDULE_V1",
        rows=(
            SealedScheduleRow(
                team="USC", week=0, opponent="San José State", location="home",
                kickoff_at="2026-08-29T12:00:00-07:00",
            ),
            SealedScheduleRow(
                team="USC", week=1, opponent="Fresno State", location="home",
                kickoff_at="2026-09-04T18:00:00-07:00",
            ),
        ),
    )


def _legacy_usc_week_one(db_session):
    player = Player(name="USC Early QB", position="QB", school="USC")
    game = Game(
        external_id="401864494", season=2026, week=1, home_team="USC", away_team="San José State",
        start_date=datetime(2026, 8, 29, 19, tzinfo=timezone.utc), home_points=42, away_points=26,
        schedule_status="final",
    )
    db_session.add_all([player, game])
    db_session.flush()
    db_session.add_all([
        TeamSchedule(
            team_name="USC", season=2026, week=1, game_id=game.id, opponent_name="San José State",
            location="home", is_bye=False, game_date=datetime(2026, 8, 29).date(),
            kickoff_at=datetime(2026, 8, 29, 19, tzinfo=timezone.utc), date_confirmed=True,
        ),
        PlayerGameStat(
            player_id=player.id, game_id=game.id, season=2026, week=1, source="espn_final_boxscore",
            stats={"pass_yards": 286, "pass_tds": 2},
        ),
        PlayerStat(
            player_id=player.id, season=2026, week=1, source="espn_final_boxscore", verified=True,
            stats={"pass_yards": 286, "pass_tds": 2},
        ),
    ])
    db_session.commit()
    return player, game


def test_reconciliation_repairs_week_zero_history_and_next_game_without_league_week_mutation(db_session, monkeypatch):
    monkeypatch.setattr(reconciliation, "load_sealed_schedule_snapshot", lambda _season: _snapshot())
    player, original_game = _legacy_usc_week_one(db_session)

    report = reconciliation.reconcile_early_player_game_schedules(
        db_session,
        season=2026,
        apply=True,
        teams={"USC"},
    )
    db_session.commit()

    assert report.unresolved == ()
    assert report.repaired_teams == ("USC",)
    assert report.created_next_games == 1
    assert report.created_next_schedules == 1
    assert report.moved_player_game_stats == 1
    assert report.moved_player_stats == 1
    assert db_session.get(Game, original_game.id).week == 0
    assert db_session.query(PlayerGameStat).filter_by(player_id=player.id).one().week == 0
    assert db_session.query(PlayerStat).filter_by(player_id=player.id).one().week == 0

    schedules = db_session.query(TeamSchedule).filter_by(team_name="USC", season=2026).order_by(TeamSchedule.week).all()
    assert [(row.week, row.opponent_name) for row in schedules] == [(0, "San José State"), (1, "Fresno State")]
    assert schedules[0].game_id == original_game.id
    assert schedules[1].kickoff_at.replace(tzinfo=timezone.utc) == datetime(2026, 9, 5, 1, tzinfo=timezone.utc)

    game_log = build_player_game_log(db_session, player, season=2026)
    assert [(row.week, row.opponent_name, row.game_status) for row in game_log.games] == [
        (0, "San José State", "final"),
        (1, "Fresno State", "scheduled"),
    ]
    assert game_log.games[0].stats.stats["pass_yards"] == 286
    display = player_game_display_state(
        db_session, player=player, season=2026, now=datetime(2026, 9, 4, 18, tzinfo=timezone.utc)
    )
    assert (display.state, display.week, display.opponent_name) == ("upcoming", 1, "Fresno State")


def test_reconciliation_dry_run_does_not_change_legacy_rows(db_session, monkeypatch):
    monkeypatch.setattr(reconciliation, "load_sealed_schedule_snapshot", lambda _season: _snapshot())
    player, game = _legacy_usc_week_one(db_session)

    report = reconciliation.reconcile_early_player_game_schedules(db_session, season=2026, apply=False)
    db_session.rollback()

    assert report.applied is False
    assert report.repaired_teams == ("USC",)
    assert db_session.get(Game, game.id).week == 1
    assert db_session.query(PlayerGameStat).filter_by(player_id=player.id).one().week == 1


def test_reconciliation_uses_the_completed_row_when_a_week_zero_placeholder_is_duplicated(db_session, monkeypatch):
    monkeypatch.setattr(reconciliation, "load_sealed_schedule_snapshot", lambda _season: _snapshot())
    player, completed_game = _legacy_usc_week_one(db_session)
    placeholder_game = Game(
        external_id="placeholder-usc-sjs", season=2026, week=0,
        home_team="USC", away_team="San José State",
    )
    db_session.add(placeholder_game)
    db_session.flush()
    db_session.add(
        TeamSchedule(
            team_name="USC", season=2026, week=0, game_id=placeholder_game.id,
            opponent_name="San José State", location="home", is_bye=False,
            game_date=datetime(2026, 8, 29).date(),
        )
    )
    db_session.commit()

    report = reconciliation.reconcile_early_player_game_schedules(db_session, season=2026, apply=True)
    db_session.commit()

    assert report.unresolved == ()
    schedules = db_session.query(TeamSchedule).filter_by(team_name="USC", season=2026).all()
    assert [(row.week, row.game_id) for row in schedules if row.opponent_name == "San José State"] == [
        (0, completed_game.id)
    ]
    assert db_session.get(Game, completed_game.id).week == 0
    assert db_session.get(Game, placeholder_game.id) is not None
    assert db_session.query(PlayerGameStat).filter_by(player_id=player.id).one().week == 0
