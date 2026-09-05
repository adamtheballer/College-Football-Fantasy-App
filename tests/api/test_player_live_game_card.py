from datetime import datetime, timedelta, timezone

import pytest

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll, ProviderGameSnapshot
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.player_game_display import player_game_display_state


def _live_fixture(db, position="WR", stats=None):
    kickoff = datetime(2026, 9, 5, 0, tzinfo=timezone.utc)
    player = Player(name="Live Sooner", school="Oklahoma", position=position)
    game = Game(external_id="live-ou", season=2026, week=1, home_team="Oklahoma", away_team="UTEP",
                start_date=kickoff, schedule_status="pre")
    next_game = Game(external_id="next-ou", season=2026, week=2, home_team="Oklahoma", away_team="Michigan",
                     start_date=kickoff + timedelta(days=7), schedule_status="pre")
    db.add_all([player, game, next_game])
    db.flush()
    for row in (game, next_game):
        db.add(TeamSchedule(team_name="Oklahoma", season=2026, week=row.week, game_id=row.id,
                            opponent_name=row.away_team, location="home", is_bye=False,
                            kickoff_at=row.start_date, game_date=row.start_date.date()))
    snapshot = ProviderGameSnapshot(provider="espn", provider_game_id=game.external_id, season=2026,
        week=1, status="live", captured_at=kickoff + timedelta(minutes=20), snapshot_hash="accepted-live",
        accepted=True, event_state="live", normalized_rows=[{"player_id": player.id, "stats": stats or {"Receptions": 3, "ReceivingYards": 42}}])
    poll = ProviderGamePoll(provider="espn", provider_game_id=game.external_id, season=2026, week=1,
                            status="live", accepted_snapshot_hash=snapshot.snapshot_hash)
    db.add_all([snapshot, poll])
    db.commit()
    return player, game, snapshot, poll


@pytest.mark.parametrize("position,stats", [
    ("WR", {"Receptions": 3, "ReceivingYards": 42}),
    ("RB", {"RushingAttempts": 12, "RushingYards": 81}),
    ("QB", {"PassingAttempts": 18, "PassingYards": 192}),
    ("TE", {"Receptions": 4, "ReceivingYards": 60}),
    ("K", {"ExtraPointsMade": 2}),
])
def test_card_and_log_use_same_live_game_stats_without_weekly_projection(client, db_session, position, stats):
    player, game, snapshot, poll = _live_fixture(db_session, position, stats)
    state = player_game_display_state(db_session, player=player, season=2026,
                                     now=snapshot.captured_at)
    assert state.state == "live"
    assert state.opponent_name == "UTEP" and state.week == 1
    assert state.stats == stats
    assert state.kickoff_at == datetime(2026, 9, 5, 0, tzinfo=timezone.utc)
    response = client.get(f"/players/{player.id}/game-log?season=2026")
    assert response.status_code == 200
    rows = response.json()["games"]
    assert rows[0]["game_status"] == "active"
    assert rows[0]["stats"]["stats"] == state.stats
    assert rows[1]["stats"] is None
    assert db_session.query(PlayerStat).count() == 0  # Read-only, no league-score promotion.


def test_rejected_snapshots_cannot_replace_live_card_stats(client, db_session):
    player, game, snapshot, poll = _live_fixture(db_session)
    db_session.add(ProviderGameSnapshot(provider="espn", provider_game_id=game.external_id, season=2026,
        week=1, status="live", captured_at=snapshot.captured_at + timedelta(minutes=1),
        snapshot_hash="rejected", accepted=False, normalized_rows=[{"player_id": player.id, "stats": {"ReceivingYards": 999}}]))
    db_session.commit()
    state = player_game_display_state(db_session, player=player, season=2026, now=snapshot.captured_at)
    assert state.stats["ReceivingYards"] == 42


def test_refresh_and_final_transition_keep_the_same_game(client, db_session):
    player, game, snapshot, poll = _live_fixture(db_session)
    newer = ProviderGameSnapshot(provider="espn", provider_game_id=game.external_id, season=2026,
        week=1, status="final", captured_at=snapshot.captured_at + timedelta(hours=3),
        snapshot_hash="accepted-final", accepted=True, normalized_rows=[{"player_id": player.id, "stats": {"ReceivingYards": 100, "Receptions": 7}}])
    db_session.add(newer)
    poll.accepted_snapshot_hash = newer.snapshot_hash
    poll.status = "final"
    db_session.commit()
    state = player_game_display_state(db_session, player=player, season=2026, now=newer.captured_at)
    assert state.state == "completed" and state.week == 1
    assert state.stats["ReceivingYards"] == 100
    row = client.get(f"/players/{player.id}/game-log?season=2026").json()["games"][0]
    assert row["game_status"] == "final" and row["stats"]["stats"]["ReceivingYards"] == 100


def test_missing_player_stats_stays_on_live_event_and_does_not_invent_zero(db_session):
    player, game, snapshot, poll = _live_fixture(db_session)
    snapshot.normalized_rows = []
    db_session.commit()
    state = player_game_display_state(db_session, player=player, season=2026, now=snapshot.captured_at)
    assert state.state == "live" and state.week == 1 and state.stats is None


def test_just_started_game_waits_for_feed_instead_of_skipping_to_next_week(db_session):
    player, game, snapshot, poll = _live_fixture(db_session)
    poll.accepted_snapshot_hash = None
    db_session.commit()
    state = player_game_display_state(db_session, player=player, season=2026, now=snapshot.captured_at)
    assert state.state == "awaiting_live" and state.week == 1 and state.stats is None


def test_weekly_stat_from_other_event_does_not_leak_into_game_log(client, db_session):
    player, game, snapshot, poll = _live_fixture(db_session)
    snapshot.normalized_rows = []
    db_session.add(PlayerStat(player_id=player.id, season=2026, week=1, source="espn",
                             stats={"EventID": "another-game", "ReceivingYards": 500}))
    db_session.commit()
    row = client.get(f"/players/{player.id}/game-log?season=2026").json()["games"][0]
    assert row["game_status"] == "active" and row["stats"] is None
