from datetime import datetime, timedelta, timezone

import pytest

from collegefootballfantasy_api.app.api.routes import injuries as routes
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.services.league_roster_matchup import _injury_status_by_player
from collegefootballfantasy_api.app.services.sportsdata_sync import _official_availability_status


def test_live_feed_follows_server_week_and_keeps_season_absences(client, db_session, monkeypatch):
    players = [Player(name=name, school="Texas", position="RB") for name in ("Weekly", "Season absence", "Old injury", "Future injury")]
    db_session.add_all(players)
    db_session.flush()
    db_session.add_all([
        Injury(player_id=players[0].id, season=2026, week=6, status="Probable"),
        Injury(player_id=players[1].id, season=2026, week=2, status="OUT_FOR_SEASON"),
        Injury(player_id=players[2].id, season=2026, week=1, status="OUT"),
        Injury(player_id=players[3].id, season=2026, week=7, status="OUT_FOR_SEASON"),
    ])
    db_session.commit()
    monkeypatch.setattr(routes, "calendar_cfb_week", lambda _season: 6)
    body = client.get("/injuries?season=2026").json()
    assert (body["season"], body["week"]) == (2026, 6)
    assert {r["player_name"]: r["status"] for r in body["data"]} == {"Weekly": "PROBABLE", "Season absence": "OUT_FOR_SEASON"}
    assert client.get("/injuries?season=2026&week=6&conference=ALL").json() == body
    statuses = _injury_status_by_player(db_session, season=2026, week=6, player_ids={p.id for p in players})
    assert statuses == {players[0].id: "PROBABLE", players[1].id: "OUT_FOR_SEASON"}


def test_newer_available_report_clears_older_out_across_all_readers(client, db_session):
    p = Player(name="Recovered", school="Georgia", position="WR")
    db_session.add(p)
    db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Injury(player_id=p.id, season=2026, week=6, status="OUT", updated_at=now-timedelta(hours=1)),
        Injury(player_id=p.id, season=2026, week=6, status="FULL", updated_at=now),
    ])
    db_session.commit()
    feed = client.get("/injuries?season=2026&week=6").json()
    assert feed["total"] == 1
    assert feed["data"][0]["status"] == "FULL"
    assert client.get("/stats/injuries?season=2026&week=6").json()["data"][0]["status"] == "FULL"
    assert client.get(f"/players/{p.id}/card?injury_season=2026&injury_week=6").json()["current_injury_status"] == "FULL"
    assert _injury_status_by_player(db_session, season=2026, week=6, player_ids={p.id}) == {}


def test_sourced_reports_expose_provenance_and_unreported_is_not_full(client, db_session):
    p = Player(name="Sourced", school="Ohio State", position="QB")
    db_session.add(p)
    db_session.flush()
    db_session.add(Injury(player_id=p.id, season=2026, week=6, status="DOUBTFUL"))
    db_session.add(PlayerAvailabilityEvent(player_id=p.id, season=2026, week=6, status="DOUBTFUL", effective_from_week=6, reviewed=True, source="official_big10_availability_report", source_url="https://bigten.org/fb/availability-reports/"))
    db_session.commit()
    body = client.get("/injuries?season=2026&week=6&conference=BIG10").json()
    assert body["data"][0]["source_url"] == "https://bigten.org/fb/availability-reports/"
    assert client.get(f"/injuries/player/{p.id}?season=2026&week=7").json()["status"] == "UNREPORTED"
    assert client.get("/injuries/player/999999?season=2026&week=7").status_code == 404


@pytest.mark.parametrize("status", ["Doubtful", "Probable", "Questionable", "Suspended", "Inactive", "Day-to-day"])
def test_official_import_preserves_designation(status):
    assert _official_availability_status(status, None) == status.upper().replace("-", "_")


def test_unknown_official_designation_never_becomes_healthy():
    assert _official_availability_status("Not yet evaluated", None) == "TBD"


def test_independent_fantasy_players_are_included_without_expanding_to_other_schools(client, db_session):
    players = [Player(name="Independent injured", school="NOTRE DAME", position="WR"),
               Player(name="Outside fantasy pool", school="Boise State", position="WR")]
    db_session.add_all(players)
    db_session.flush()
    for player in players:
        db_session.add(Injury(player_id=player.id, season=2026, week=8, status="OUT_FOR_SEASON"))
    db_session.commit()
    rows = client.get("/injuries?season=2026&week=8").json()["data"]
    assert [(r["player_id"], r["team"], r["conference"]) for r in rows] == [(players[0].id, "Notre Dame", "INDEPENDENT")]
    assert client.get("/injuries?season=2026&week=8&conference=INDEPENDENT").json()["data"] == rows
    assert client.get("/injuries?season=2026&week=8&conference=ACC").json()["data"] == []
    assert client.get(f"/injuries/player/{players[0].id}?season=2026&week=8").json()["conference"] == "INDEPENDENT"
    stats_rows = client.get("/stats/injuries?season=2026&week=8&conference=INDEPENDENT").json()["data"]
    assert [(r["player_id"], r["conference"], r["status"]) for r in stats_rows] == [(players[0].id, "INDEPENDENT", "OUT_FOR_SEASON")]


@pytest.mark.parametrize("query", ["week=0", "week=31", "season=0"])
def test_injury_query_rejects_invalid_period(client, query):
    assert client.get(f"/injuries?{query}").status_code == 422


def test_bounded_reviewed_absence_survives_bye_and_expires_without_carrying_normal_out(client, db_session):
    from collegefootballfantasy_api.app.services.availability_corrections import MANUAL_CORROBORATED_SOURCE
    p = Player(name="Long absence", school="Ohio State", position="QB")
    db_session.add(p); db_session.flush()
    db_session.add_all([
        Injury(player_id=p.id, season=2026, week=8, status="OUT", return_timeline="Out indefinitely"),
        PlayerAvailabilityEvent(player_id=p.id, season=2026, week=8, status="OUT",
            source=MANUAL_CORROBORATED_SOURCE, source_url="https://example.test/coach",
            effective_from_week=8, effective_until_week=11, reviewed=True),
    ])
    db_session.commit()
    for week in (8, 9, 10, 11):
        assert client.get(f"/injuries/player/{p.id}?season=2026&week={week}").json()["status"] == "OUT"
        assert _injury_status_by_player(db_session, season=2026, week=week, player_ids={p.id}) == {p.id:"OUT"}
    assert client.get(f"/injuries/player/{p.id}?season=2026&week=12").json()["status"] == "UNREPORTED"
    assert client.get(f"/injuries/player/{p.id}?season=2026&week=7").json()["status"] == "UNREPORTED"


def test_newer_week_return_clears_bounded_manual_and_season_absence(db_session):
    from collegefootballfantasy_api.app.services.availability_corrections import MANUAL_CORROBORATED_SOURCE
    from collegefootballfantasy_api.app.services.injury_status import reviewed_injuries_for_week
    p = Player(name="Verified return", school="UCLA", position="QB")
    db_session.add(p); db_session.flush()
    db_session.add_all([
        Injury(player_id=p.id, season=2026, week=8, status="OUT_FOR_SEASON"),
        Injury(player_id=p.id, season=2026, week=9, status="FULL"),
        PlayerAvailabilityEvent(player_id=p.id, season=2026, week=8, status="OUT_FOR_SEASON",
            source=MANUAL_CORROBORATED_SOURCE, source_url="https://example.test/coach",
            effective_from_week=8, effective_until_week=15, reviewed=True),
    ])
    db_session.commit()
    assert reviewed_injuries_for_week(db_session,season=2026,week=9)[p.id].status == "FULL"
    assert p.id not in reviewed_injuries_for_week(db_session,season=2026,week=10)


def test_newer_same_week_full_clears_a_bounded_assertion(db_session):
    from collegefootballfantasy_api.app.services.availability_corrections import MANUAL_CORROBORATED_SOURCE
    from collegefootballfantasy_api.app.services.injury_status import reviewed_injuries_for_week
    p=Player(name="Same week recovery",school="UCLA",position="QB")
    db_session.add(p);db_session.flush()
    now=datetime.now(timezone.utc)
    db_session.add_all([
        Injury(player_id=p.id,season=2026,week=8,status="OUT",updated_at=now-timedelta(hours=3)),
        PlayerAvailabilityEvent(player_id=p.id,season=2026,week=8,status="OUT",
            source=MANUAL_CORROBORATED_SOURCE,source_url="https://example.test/coach",
            effective_from_week=8,effective_until_week=15,reviewed=True,created_at=now-timedelta(hours=2)),
        Injury(player_id=p.id,season=2026,week=8,status="FULL",updated_at=now),
    ])
    db_session.commit()
    assert reviewed_injuries_for_week(db_session,season=2026,week=8)[p.id].status == "FULL"


def test_repeated_weekly_out_does_not_clear_a_confirmed_long_absence(db_session):
    from collegefootballfantasy_api.app.services.availability_corrections import MANUAL_CORROBORATED_SOURCE
    from collegefootballfantasy_api.app.services.injury_status import reviewed_injuries_for_week
    p=Player(name="Repeating OUT",school="UCLA",position="QB")
    db_session.add(p);db_session.flush()
    db_session.add_all([
        Injury(player_id=p.id,season=2026,week=8,status="OUT_FOR_SEASON"),
        Injury(player_id=p.id,season=2026,week=9,status="OUT"),
        PlayerAvailabilityEvent(player_id=p.id,season=2026,week=8,status="OUT_FOR_SEASON",
            source=MANUAL_CORROBORATED_SOURCE,source_url="https://example.test/coach",
            effective_from_week=8,effective_until_week=15,reviewed=True),
    ])
    db_session.commit()
    assert reviewed_injuries_for_week(db_session,season=2026,week=9)[p.id].status == "OUT_FOR_SEASON"
    assert reviewed_injuries_for_week(db_session,season=2026,week=10)[p.id].status == "OUT_FOR_SEASON"
