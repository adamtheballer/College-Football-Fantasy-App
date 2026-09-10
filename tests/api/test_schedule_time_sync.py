from datetime import datetime, timezone

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.schedule_sync_issue import ScheduleSyncIssue
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.player_game_log import build_player_game_log
from collegefootballfantasy_api.app.services.schedule_time_sync import (
    ProviderScheduleGame,
    _espn_events,
    apply_manual_kickoff_override,
    run_due_schedule_sync,
    sync_remaining_schedule_times,
    sync_schedule_times,
)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _event(*, kickoff_at: datetime | None = datetime(2026, 9, 12, 23, 30, tzinfo=timezone.utc)) -> ProviderScheduleGame:
    return ProviderScheduleGame(
        external_game_id="401999001",
        season=2026,
        week=2,
        home_team="Miami",
        away_team="Florida State",
        kickoff_at=kickoff_at,
        venue="Hard Rock Stadium",
        network="ABC",
    )


def _rows(db_session, *, kickoff_at=None, manual_override=False):
    home = TeamSchedule(
        team_name="Miami (FL)", season=2026, week=2, opponent_name="Florida State",
        location="home", is_bye=False, kickoff_at=kickoff_at, manual_override=manual_override,
    )
    away = TeamSchedule(
        team_name="Florida State", season=2026, week=2, opponent_name="Miami",
        location="away", is_bye=False, kickoff_at=kickoff_at,
    )
    db_session.add_all([home, away])
    db_session.commit()
    return home, away


def test_tbd_is_replaced_in_canonical_schedule_and_linked_game(db_session):
    home, away = _rows(db_session)

    summary = sync_schedule_times(
        db_session, season=2026, week=2, source="espn", force_current_week=True, provider_events=[_event()],
    )
    db_session.commit()

    db_session.refresh(home)
    db_session.refresh(away)
    assert summary.games_updated == 2
    assert _as_utc(home.kickoff_at) == datetime(2026, 9, 12, 23, 30, tzinfo=timezone.utc)
    assert _as_utc(away.kickoff_at) == _as_utc(home.kickoff_at)
    assert home.time_status == away.time_status == "confirmed"
    assert home.game_id == away.game_id
    game = db_session.get(Game, home.game_id)
    assert game is not None and game.external_id == "401999001"
    assert _as_utc(game.start_date) == _as_utc(home.kickoff_at)


def test_espn_schedule_uses_school_name_not_mascot_display_name(monkeypatch):
    import collegefootballfantasy_api.app.services.schedule_time_sync as schedule_sync

    class FakeESPNClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get_scoreboard_events(self, **_kwargs):
            return [{
                "id": "401999001",
                "competitions": [{
                    "date": "2026-09-12T23:30:00Z",
                    "competitors": [
                        {"homeAway": "home", "team": {"shortDisplayName": "Miami", "displayName": "Miami Hurricanes"}},
                        {"homeAway": "away", "team": {"shortDisplayName": "Florida State", "displayName": "Florida State Seminoles"}},
                    ],
                }],
            }]

    monkeypatch.setattr(schedule_sync, "ESPNClient", FakeESPNClient)

    event = _espn_events(season=2026, week=2)[0]

    assert event.home_team == "Miami"
    assert event.away_team == "Florida State"


def test_espn_team_schedule_fallback_repairs_a_scoreboard_omission(db_session, monkeypatch):
    """A valid team schedule must repair an otherwise omitted scoreboard game."""

    import collegefootballfantasy_api.app.services.schedule_time_sync as schedule_sync

    home, away = _rows(db_session)
    monkeypatch.setattr(schedule_sync, "fetch_schedule_events", lambda **_kwargs: [])
    observed_team_names: list[str] = []

    def team_schedule_fallback(*, team_names, **_kwargs):
        observed_team_names.extend(team_names)
        return [_event()], 1

    monkeypatch.setattr(schedule_sync, "_espn_team_schedule_events", team_schedule_fallback)

    summary = sync_schedule_times(
        db_session,
        season=2026,
        week=2,
        source="espn",
        force_current_week=True,
    )
    db_session.commit()

    db_session.refresh(home)
    db_session.refresh(away)
    assert observed_team_names == ["Miami (FL)"]
    assert summary.team_schedule_fallback_teams == 1
    assert summary.team_schedule_fallback_games == 1
    assert summary.games_updated == 2
    assert _as_utc(home.kickoff_at) == _as_utc(away.kickoff_at)


def test_remaining_season_sync_hydrates_each_future_nonbye_week(db_session, monkeypatch):
    """Future matchup pages are populated before their week becomes active."""

    import collegefootballfantasy_api.app.services.schedule_time_sync as schedule_sync

    home = TeamSchedule(team_name="Miami (FL)", season=2026, week=3, opponent_name="Florida State", location="home", is_bye=False)
    away = TeamSchedule(team_name="Florida State", season=2026, week=3, opponent_name="Miami", location="away", is_bye=False)
    db_session.add_all([home, away])
    db_session.commit()
    future_event = ProviderScheduleGame(
        external_game_id="401999003",
        season=2026,
        week=3,
        home_team="Miami",
        away_team="Florida State",
        kickoff_at=datetime(2026, 9, 19, 23, 30, tzinfo=timezone.utc),
    )
    calls: list[tuple[set[int], list[str]]] = []

    def season_fallback(*, weeks, team_names, **_kwargs):
        calls.append((weeks, list(team_names)))
        return [future_event], 1

    monkeypatch.setattr(schedule_sync, "_espn_team_schedule_events_for_weeks", season_fallback)

    summaries = sync_remaining_schedule_times(
        db_session,
        season=2026,
        start_week=2,
        source="espn",
    )
    db_session.commit()

    db_session.refresh(home)
    db_session.refresh(away)
    assert calls == [({3}, ["Miami (FL)"])]
    assert len(summaries) == 1
    assert summaries[0].games_updated == 2
    assert _as_utc(home.kickoff_at) == datetime(2026, 9, 19, 23, 30, tzinfo=timezone.utc)
    assert _as_utc(away.kickoff_at) == _as_utc(home.kickoff_at)


def test_confirmed_time_is_never_downgraded_when_provider_time_is_missing(db_session):
    kickoff = datetime(2026, 9, 12, 23, 30, tzinfo=timezone.utc)
    home, _away = _rows(db_session, kickoff_at=kickoff)

    summary = sync_schedule_times(
        db_session, season=2026, week=2, source="espn", force_current_week=True, provider_events=[_event(kickoff_at=None)],
    )
    db_session.commit()

    db_session.refresh(home)
    assert _as_utc(home.kickoff_at) == kickoff
    assert summary.games_updated == 0
    assert summary.games_still_missing_time == 2
    issue = db_session.query(ScheduleSyncIssue).filter_by(team_name="Miami (FL)", issue_type="provider_missing_time").one()
    assert issue.current_value == "2026-09-12T23:30:00"


def test_manual_override_is_not_overwritten(db_session):
    previous = datetime(2026, 9, 12, 20, 0, tzinfo=timezone.utc)
    home, _away = _rows(db_session, kickoff_at=previous, manual_override=True)
    home.manual_override_reason = "League commissioner verified the TV update."
    db_session.commit()

    summary = sync_schedule_times(
        db_session, season=2026, week=2, source="espn", force_current_week=True, provider_events=[_event()],
    )
    db_session.commit()

    db_session.refresh(home)
    assert _as_utc(home.kickoff_at) == previous
    assert summary.skipped_manual_override == 1
    assert db_session.query(ScheduleSyncIssue).filter_by(team_name="Miami (FL)", issue_type="manual_override_skipped").count() == 1


def test_unmatched_schedule_is_logged_without_creating_a_game(db_session):
    db_session.add(TeamSchedule(team_name="Texas", season=2026, week=2, opponent_name="UTEP", location="home", is_bye=False))
    db_session.commit()

    summary = sync_schedule_times(
        db_session, season=2026, week=2, source="espn", force_current_week=True, provider_events=[_event()],
    )
    db_session.commit()

    assert summary.issues["game_not_found"] == 1
    assert db_session.query(Game).count() == 0
    assert db_session.query(ScheduleSyncIssue).filter_by(issue_type="game_not_found").count() == 1


def test_repeat_sync_is_idempotent_and_does_not_duplicate_game_or_issue(db_session):
    _rows(db_session)
    first = sync_schedule_times(
        db_session, season=2026, week=2, source="espn", force_current_week=True, provider_events=[_event()],
    )
    db_session.commit()
    second = sync_schedule_times(
        db_session, season=2026, week=2, source="espn", force_current_week=True, provider_events=[_event()],
    )
    db_session.commit()

    assert first.games_updated == 2
    assert second.games_updated == 0
    assert db_session.query(Game).count() == 1
    assert db_session.query(ScheduleSyncIssue).count() == 0


def test_manual_override_updates_both_sides_of_a_linked_game(db_session):
    home, away = _rows(db_session)
    sync_schedule_times(
        db_session, season=2026, week=2, source="espn", force_current_week=True, provider_events=[_event()],
    )
    db_session.commit()

    kickoff = datetime(2026, 9, 12, 20, 0, tzinfo=timezone.utc)
    apply_manual_kickoff_override(
        db_session, schedule_id=home.id, kickoff_at=kickoff, reason="Commissioner verified the TV announcement.", actor_user_id=7,
    )
    db_session.commit()
    db_session.refresh(home)
    db_session.refresh(away)

    assert _as_utc(home.kickoff_at) == kickoff
    assert _as_utc(away.kickoff_at) == kickoff
    assert home.time_status == away.time_status == "manual_override"
    assert home.manual_override is away.manual_override is True


def test_player_game_log_reads_the_canonical_synced_kickoff(db_session):
    home, _away = _rows(db_session)
    player = Player(name="Schedule Test Receiver", position="WR", school="Miami (FL)")
    db_session.add(player)
    db_session.commit()

    sync_schedule_times(
        db_session, season=2026, week=2, source="espn", force_current_week=True, provider_events=[_event()],
    )
    db_session.commit()

    game_log = build_player_game_log(db_session, player, season=2026)
    assert game_log.games[0].schedule_id == home.id
    assert _as_utc(game_log.games[0].kickoff_at) == datetime(2026, 9, 12, 23, 30, tzinfo=timezone.utc)


def test_due_sync_records_provider_failure_without_crashing_the_worker(db_session, monkeypatch):
    import collegefootballfantasy_api.app.services.schedule_time_sync as schedule_sync

    monkeypatch.setattr(settings, "schedule_sync_enabled", True)
    monkeypatch.setattr(settings, "schedule_sync_source", "espn")
    monkeypatch.setattr(settings, "schedule_sync_hour_et", 7)

    def unavailable(**_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(schedule_sync, "fetch_schedule_events", unavailable)
    result = run_due_schedule_sync(
        db_session,
        season=2026,
        now=datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc),  # Tuesday, 9:00 AM Eastern
    )

    assert result["status"] == "failed"
    assert "provider unavailable" in str(result["error"])
    retry = run_due_schedule_sync(
        db_session,
        season=2026,
        now=datetime(2026, 9, 8, 13, 5, tzinfo=timezone.utc),
    )
    assert retry["status"] == "retry_backoff"


def test_due_sync_persists_json_safe_timestamp_audit_metadata(db_session, monkeypatch):
    import collegefootballfantasy_api.app.services.schedule_time_sync as schedule_sync

    monkeypatch.setattr(settings, "schedule_sync_enabled", True)
    monkeypatch.setattr(settings, "schedule_sync_source", "espn")
    monkeypatch.setattr(settings, "schedule_sync_hour_et", 7)
    monkeypatch.setattr(schedule_sync, "fetch_schedule_events", lambda **_kwargs: [])

    result = run_due_schedule_sync(
        db_session,
        season=2026,
        now=datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc),  # Tuesday, 9:00 AM Eastern
    )

    assert result["status"] == "completed"
    assert isinstance(result["started_at"], str)
    assert isinstance(result["completed_at"], str)
