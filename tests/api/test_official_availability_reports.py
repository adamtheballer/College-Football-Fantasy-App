from collegefootballfantasy_api.app.integrations.conference_availability_reports import (
    ConferenceAvailabilityReportClient,
    ConferenceReportUnavailable,
    ConferenceReportSource,
    _embedded_report_url,
    parse_report_document,
)
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.models.player_news_event import PlayerNewsEvent
from collegefootballfantasy_api.app.services.sportsdata_sync import (
    _availability_multiplier,
    _official_availability_status,
    _upsert_official_availability_rows,
)
from bs4 import BeautifulSoup


def test_official_report_parser_requires_a_recognized_public_table():
    html = """
    <table>
      <tr><th>Player</th><th>Team</th><th>Position</th><th>Status</th><th>Notes</th></tr>
      <tr><td>Cam Coleman</td><td>Auburn</td><td>WR</td><td>Questionable</td><td>Shoulder</td></tr>
    </table>
    """
    rows = parse_report_document(html, conference="SEC", source_url="https://example.test/report")
    assert rows == [{
        "player_name": "Cam Coleman",
        "team_name": "Auburn",
        "position": "WR",
        "status": "Questionable",
        "injury": None,
        "return_timeline": None,
        "practice_level": None,
        "notes": "Shoulder",
        "conference": "SEC",
        "source_url": "https://example.test/report",
    }]

    try:
        parse_report_document("<p>Report pending</p>", conference="SEC", source_url="https://example.test/report")
    except ConferenceReportUnavailable:
        pass
    else:  # pragma: no cover - explicit failure makes the safety contract clear
        raise AssertionError("unreadable reports must not be interpreted as an empty report")


def test_report_parser_accepts_explicit_conference_heading_variants_and_skips_tracking_frames():
    html = """
    <table>
      <tr><th>Student-Athlete</th><th>Institution</th><th>Pos</th><th>Availability Status</th></tr>
      <tr><td>Cam Coleman</td><td>Auburn</td><td>WR</td><td>Out</td></tr>
    </table>
    <iframe src="https://ads.example.test/tracker"></iframe>
    <iframe src="https://confinjrepxyz.example.test?source=SECreports"></iframe>
    """
    rows = parse_report_document(html, conference="SEC", source_url="https://example.test/report")
    assert rows[0]["player_name"] == "Cam Coleman"
    assert rows[0]["team_name"] == "Auburn"
    assert rows[0]["status"] == "Out"
    assert _embedded_report_url(BeautifulSoup(html, "html.parser"), "https://example.test/report") == "https://confinjrepxyz.example.test?source=SECreports"


def test_official_ir_policy_requires_an_explicit_four_week_minimum():
    assert _official_availability_status("Out", "2-4 weeks") == "OUT"
    assert _official_availability_status("Out", "4-6 weeks") == "IR"
    assert _official_availability_status("Out", "at least four weeks") == "IR"
    assert _official_availability_status("Out for season", None) == "IR"
    assert _official_availability_status("Questionable", None) == "QUESTIONABLE"


def test_questionable_availability_retains_seventy_percent_of_projection():
    assert _availability_multiplier("QUESTIONABLE") == (0.7, 0.7)


def test_unchanged_questionable_report_repairs_an_older_cached_multiplier(db_session):
    player = Player(name="Questionable Cache", school="Auburn", position="WR")
    db_session.add(player)
    db_session.commit()
    row = {
        "player_name": "Questionable Cache",
        "team_name": "Auburn",
        "position": "WR",
        "status": "Questionable",
        "injury": "Shoulder",
        "return_timeline": None,
        "practice_level": "Limited",
        "notes": "Official report",
        "conference": "SEC",
        "source_url": "https://www.secsports.com/fbreports",
    }
    _upsert_official_availability_rows(db_session, season=2026, week=1, rows=[row])
    event = db_session.query(PlayerAvailabilityEvent).filter_by(player_id=player.id).one()
    event.probability_active = 0.5
    event.availability_multiplier = 0.5
    db_session.commit()

    changes = _upsert_official_availability_rows(db_session, season=2026, week=1, rows=[row])

    repaired = db_session.query(PlayerAvailabilityEvent).filter_by(player_id=player.id).one()
    assert changes["unchanged"] == 1
    assert db_session.query(PlayerAvailabilityEvent).filter_by(player_id=player.id).count() == 1
    assert repaired.probability_active == 0.7
    assert repaired.availability_multiplier == 0.7


def test_browser_renderer_uses_an_injected_public_document_for_a_js_shell():
    source = ConferenceReportSource("SEC", "https://www.secsports.com/fbreports")
    client = ConferenceAvailabilityReportClient(
        rendered_document=lambda received_source: (
            "<table><tr><th>Player</th><th>Team</th><th>Status</th></tr>"
            "<tr><td>Cam Coleman</td><td>Auburn</td><td>Out</td></tr></table>"
            if received_source == source
            else ""
        ),
    )
    rendered = client._render_public_document(source)
    rows = parse_report_document(rendered, conference=source.conference, source_url=source.url)
    assert rows[0]["player_name"] == "Cam Coleman"


def test_official_sync_only_accepts_exact_supported_p4_players_and_is_idempotent(db_session):
    cam = Player(name="Cam Coleman", school="Auburn", position="WR")
    defensive_player = Player(name="Defender Test", school="Auburn", position="LB")
    db_session.add_all([cam, defensive_player])
    db_session.commit()

    row = {
        "player_name": "Cam Coleman",
        "team_name": "Auburn",
        "position": "WR",
        "status": "Out",
        "injury": "Shoulder",
        "return_timeline": "2 weeks",
        "practice_level": None,
        "notes": "Official report",
        "conference": "SEC",
        "source_url": "https://www.secsports.com/fbreports",
    }
    changes = _upsert_official_availability_rows(db_session, season=2026, week=1, rows=[row])
    db_session.commit()
    assert changes["created"] == 1
    assert changes["events_created"] == 1
    injury = db_session.query(Injury).filter(Injury.player_id == cam.id).one()
    assert injury.status == "OUT"
    assert injury.return_timeline == "2 weeks"
    assert db_session.query(PlayerAvailabilityEvent).filter_by(player_id=cam.id).count() == 1
    assert db_session.query(PlayerNewsEvent).filter_by(player_id=cam.id).count() == 1

    repeat = _upsert_official_availability_rows(db_session, season=2026, week=1, rows=[row])
    assert repeat["unchanged"] == 1
    assert repeat["events_created"] == 0

    unsupported = _upsert_official_availability_rows(
        db_session,
        season=2026,
        week=1,
        rows=[{**row, "player_name": "Defender Test", "position": "LB"}],
    )
    assert unsupported["skipped"] == 1
    assert db_session.query(Injury).filter(Injury.player_id == defensive_player.id).count() == 0


def test_official_sync_uses_ir_for_an_explicit_four_week_absence(db_session):
    player = Player(name="IR Test", school="Auburn", position="RB")
    db_session.add(player)
    db_session.commit()
    row = {
        "player_name": "IR Test",
        "team_name": "Auburn",
        "position": "RB",
        "status": "Out",
        "injury": "Knee",
        "return_timeline": "4-6 weeks",
        "practice_level": None,
        "notes": None,
        "conference": "SEC",
        "source_url": "https://www.secsports.com/fbreports",
    }
    _upsert_official_availability_rows(db_session, season=2026, week=1, rows=[row])
    assert db_session.query(Injury).filter(Injury.player_id == player.id).one().status == "IR"


def test_player_card_exposes_official_availability_news(client, db_session):
    player = Player(name="Availability Card", school="Alabama", position="QB")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        PlayerAvailabilityEvent(
            player_id=player.id,
            season=2026,
            week=1,
            status="QUESTIONABLE",
            probability_active=0.7,
            availability_multiplier=0.7,
            source="official_sec_availability_report",
            source_url="https://www.secsports.com/fbreports",
            content_hash="card-news-test",
            source_reliability=1.0,
            effective_from_week=1,
            reviewed=True,
            notes="Shoulder • Limited",
        )
    )
    db_session.add(
        Injury(
            player_id=player.id,
            season=2026,
            week=1,
            status="QUESTIONABLE",
            injury="Shoulder",
            practice_level="Limited",
        )
    )
    db_session.add(
        PlayerNewsEvent(
            player_id=player.id,
            season=2026,
            week=1,
            event_type="AVAILABILITY",
            source="official_sec_availability_report",
            source_url="https://www.secsports.com/fbreports",
            content_hash="card-news-test",
            source_reliability=1.0,
            effective_from_week=1,
            reviewed=True,
            notes="Shoulder • Limited",
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/card")
    assert response.status_code == 200
    recent_news = response.json()["recent_news"]
    assert recent_news[0]["status"] == "QUESTIONABLE"
    assert recent_news[0]["source_url"] == "https://www.secsports.com/fbreports"
