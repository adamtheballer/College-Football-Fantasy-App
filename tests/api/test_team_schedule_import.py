from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services import team_schedule_import
from collegefootballfantasy_api.app.services.team_schedule_import import (
    import_team_schedule_rows,
    parse_schedule_csv,
)


HEADER = (
    "Season,Conference,Team,Week,Date,Opponent,Location,Neutral Site,Conference Game,Time (ET),TV,"
    "ESPN Schedule Hub,Primary Source,Date Confirmed\n"
)


def test_schedule_import_is_idempotent_and_preserves_tbd_kickoff(db_session):
    csv_text = HEADER + (
        "2026-27,Big10,Ohio State,0,2026-08-29,,BYE,,No,,,https://espn.example,https://source.example,Yes\n"
        "2026-27,Big10,Ohio State,1,2026-09-05,Texas,HOME,No,No,TBD,,https://espn.example,https://source.example,Yes\n"
        "2026-27,SEC,Texas,1,2026-09-05,Ohio State,AWAY,No,No,TBD,,https://espn.example,https://source.example,Yes\n"
    )
    db_session.add(Player(name="Imported Player", position="QB", school="Ohio State"))
    db_session.commit()

    rows, report = parse_schedule_csv(csv_text, season=2026)
    result = import_team_schedule_rows(db_session, rows, report, apply=True)

    assert result.has_errors is False
    assert result.inserted_schedules == 3
    assert db_session.query(TeamSchedule).count() == 3
    ohio_state_week_one = (
        db_session.query(TeamSchedule)
        .filter(TeamSchedule.team_name == "Ohio State", TeamSchedule.week == 1)
        .one()
    )
    assert ohio_state_week_one.kickoff_at is None
    assert ohio_state_week_one.game_id is not None
    assert ohio_state_week_one.venue is None

    rows, report = parse_schedule_csv(csv_text, season=2026)
    result = import_team_schedule_rows(db_session, rows, report, apply=True)

    assert result.has_errors is False
    assert result.unchanged_schedules == 3
    assert db_session.query(TeamSchedule).count() == 3


def test_schedule_import_rejects_duplicate_team_week_rows(db_session):
    csv_text = HEADER + (
        "2026-27,Big10,Ohio State,1,2026-09-05,Texas,HOME,,No,TBD,,,,Yes\n"
        "2026-27,Big10,Ohio State,1,2026-09-05,Michigan,HOME,,No,TBD,,,,Yes\n"
    )

    rows, report = parse_schedule_csv(csv_text, season=2026)
    result = import_team_schedule_rows(db_session, rows, report, apply=False)

    assert result.has_errors is True
    assert result.duplicate_team_weeks
    assert db_session.query(TeamSchedule).count() == 0


def test_schedule_import_normalizes_punctuation_for_reciprocal_opponents(db_session):
    csv_text = HEADER + (
        "2026-27,ACC,Miami,10,2026-11-07,Notre Dame,AWAY,,No,TBD,,,,Yes\n"
        "2026-27,Independent,Notre Dame,10,2026-11-07,Miami (FL),HOME,,No,TBD,,,,Yes\n"
    )

    rows, report = parse_schedule_csv(csv_text, season=2026)
    result = import_team_schedule_rows(db_session, rows, report, apply=False)

    assert result.has_errors is False
    assert result.reciprocal_conflicts == []


def test_schedule_import_dry_run_reports_plan_when_migration_is_not_applied(db_session, monkeypatch):
    csv_text = HEADER + "2026-27,Big10,Ohio State,0,2026-08-29,,BYE,,No,,,,,Yes\n"
    rows, report = parse_schedule_csv(csv_text, season=2026)
    monkeypatch.setattr(team_schedule_import, "_team_schedule_table_exists", lambda db: False)

    result = import_team_schedule_rows(db_session, rows, report, apply=False)

    assert result.has_errors is False
    assert result.schedule_schema_ready is False
    assert result.planned_schedules == 1
    assert result.planned_games == 0


def test_schedule_import_reuses_existing_provider_game_by_canonical_identity(db_session):
    from collegefootballfantasy_api.app.models.game import Game

    existing_game = Game(
        external_id="provider-2026-ohio-state-texas",
        season=2026,
        week=1,
        home_team="Ohio State",
        away_team="Texas",
        neutral_site=False,
    )
    db_session.add(existing_game)
    db_session.commit()

    csv_text = HEADER + (
        "2026-27,Big10,Ohio State,1,2026-09-05,Texas,HOME,,No,TBD,,,,Yes\n"
        "2026-27,SEC,Texas,1,2026-09-05,Ohio State,AWAY,,No,TBD,,,,Yes\n"
    )
    rows, report = parse_schedule_csv(csv_text, season=2026)
    result = import_team_schedule_rows(db_session, rows, report, apply=True)

    assert result.has_errors is False
    assert result.inserted_games == 0
    assert db_session.query(Game).count() == 1
    assert db_session.query(TeamSchedule).filter(TeamSchedule.game_id == existing_game.id).count() == 2
    assert db_session.get(Game, existing_game.id).external_id == "provider-2026-ohio-state-texas"
