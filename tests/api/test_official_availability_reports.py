from datetime import datetime, timezone

from collegefootballfantasy_api.app.integrations.conference_availability_reports import (
    ConferenceAvailabilityReportClient,
    ConferenceReportUnavailable,
    ConferenceReportSource,
    _embedded_report_url,
    _rendered_report_frame,
    parse_report_document,
)
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.models.player_news_event import PlayerNewsEvent
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.services.availability_corrections import (
    MANUAL_CORROBORATED_SOURCE,
    MANUAL_VERIFIED_SOURCE,
)
from collegefootballfantasy_api.app.services.sportsdata_sync import (
    _availability_multiplier,
    _official_availability_status,
    _upsert_official_availability_rows,
)
from bs4 import BeautifulSoup


class _FakeFrameLocator:
    def __init__(self, count: int):
        self._count = count
        self.first_requested = False

    def count(self) -> int:
        return self._count

    @property
    def first(self):
        self.first_requested = True
        return self


class _FakeFramePage:
    def __init__(self, embedded_count: int, fallback_count: int):
        self.embedded = _FakeFrameLocator(embedded_count)
        self.fallback = _FakeFrameLocator(fallback_count)
        self.selectors: list[str] = []

    def locator(self, selector: str):
        self.selectors.append(selector)
        if selector == "iframe#embedded-app":
            return self.embedded
        return self.fallback


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


def test_browser_renderer_selects_only_the_dedicated_embedded_report_frame():
    page = _FakeFramePage(embedded_count=1, fallback_count=3)

    iframe = _rendered_report_frame(page)

    assert iframe is page.embedded
    assert page.embedded.first_requested
    assert page.selectors == ["iframe#embedded-app"]


def test_browser_renderer_uses_one_fallback_report_frame_when_no_embedded_app_exists():
    page = _FakeFramePage(embedded_count=0, fallback_count=3)

    iframe = _rendered_report_frame(page)

    assert iframe is page.fallback
    assert page.fallback.first_requested
    assert len(page.selectors) == 2


def test_official_ir_policy_requires_an_explicit_four_week_minimum():
    assert _official_availability_status("Out", "2-4 weeks") == "OUT"
    assert _official_availability_status("Out", "4-6 weeks") == "IR"
    assert _official_availability_status("Out", "at least four weeks") == "IR"
    assert _official_availability_status("Out for season", None) == "OUT_FOR_SEASON"
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


def test_official_out_report_publishes_zero_projection_for_every_read_path(db_session):
    player = Player(name="Projection Safety", school="Auburn", position="RB")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        WeeklyProjection(
            player_id=player.id, season=2026, week=1, projection_version="PRESEASON",
            fantasy_points=17.5, floor=10.0, ceiling=25.0, projection_status="ACTIVE",
        )
    )
    db_session.commit()
    row = {
        "player_name": "Projection Safety", "team_name": "Auburn", "position": "RB",
        "status": "Out", "injury": "Knee", "return_timeline": "1 week",
        "practice_level": "DNP", "notes": "Official report", "conference": "SEC",
        "source_url": "https://www.secsports.com/fbreports",
    }

    _upsert_official_availability_rows(db_session, season=2026, week=1, rows=[row])
    db_session.commit()

    projection = db_session.scalar(
        current_published_projections_query(season=2026, week=1, player_ids=(player.id,))
    )
    assert projection.projection_version == "CORRECTED_INJURY"
    assert projection.projection_status == "OUT"
    assert projection.fantasy_points == 0.0


def test_reviewed_manual_override_blocks_stale_official_healthy_status_only_in_its_window(db_session):
    player = Player(name="Manual Override", school="Auburn", position="WR")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        Injury(player_id=player.id, season=2026, week=1, status="OUT", injury="Verified injury")
    )
    db_session.add(
        PlayerAvailabilityEvent(
            player_id=player.id, season=2026, week=1, status="OUT",
            probability_active=0.0, availability_multiplier=0.0,
            source=MANUAL_VERIFIED_SOURCE, source_url="https://example.test/team-report",
            source_reliability=1.0, effective_from_week=1, effective_until_week=1,
            reviewed=True, notes="Verified team report",
        )
    )
    db_session.commit()
    healthy_row = {
        "player_name": "Manual Override", "team_name": "Auburn", "position": "WR",
        "status": "Available", "injury": None, "return_timeline": None,
        "practice_level": "Full", "notes": "Stale report", "conference": "SEC",
        "source_url": "https://www.secsports.com/fbreports",
    }

    changes = _upsert_official_availability_rows(db_session, season=2026, week=1, rows=[healthy_row])

    assert changes["overrides_preserved"] == 1
    assert db_session.query(Injury).filter_by(player_id=player.id, season=2026, week=1).one().status == "OUT"


def test_reviewed_corroborated_override_also_blocks_a_stale_official_healthy_status(db_session):
    player = Player(name="Corroborated Override", school="Auburn", position="RB")
    db_session.add(player)
    db_session.flush()
    db_session.add_all(
        [
            Injury(player_id=player.id, season=2026, week=2, status="OUT", injury="Hamstring"),
            PlayerAvailabilityEvent(
                player_id=player.id, season=2026, week=2, status="OUT",
                probability_active=0.0, availability_multiplier=0.0,
                source=MANUAL_CORROBORATED_SOURCE,
                source_url="https://example.test/primary", source_reliability=1.0,
                effective_from_week=2, effective_until_week=2, reviewed=True,
                notes="Corroborated by 2 independent public reports.",
            ),
        ]
    )
    db_session.commit()
    healthy_row = {
        "player_name": "Corroborated Override", "team_name": "Auburn", "position": "RB",
        "status": "Available", "injury": None, "return_timeline": None,
        "practice_level": "Full", "notes": "Stale report", "conference": "SEC",
        "source_url": "https://www.secsports.com/fbreports",
    }

    changes = _upsert_official_availability_rows(db_session, season=2026, week=2, rows=[healthy_row])

    assert changes["overrides_preserved"] == 1
    assert db_session.query(Injury).filter_by(player_id=player.id, season=2026, week=2).one().status == "OUT"


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
            published_at=datetime(2026, 8, 24, 16, 58, tzinfo=timezone.utc),
            notes="Shoulder • Limited",
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/card")
    assert response.status_code == 200
    recent_news = response.json()["recent_news"]
    assert recent_news[0]["status"] == "QUESTIONABLE"
    assert recent_news[0]["source_url"] == "https://www.secsports.com/fbreports"
    assert datetime.fromisoformat(recent_news[0]["published_at"].replace("Z", "+00:00")) == datetime(
        2026, 8, 24, 16, 58, tzinfo=timezone.utc
    )


def test_dated_archive_chooses_final_status_and_never_guesses_dates():
    import pytest
    from collegefootballfantasy_api.app.integrations.conference_availability_reports import parse_archive_document
    html = '''<table><tr><th>Date</th><th>Team</th><th>Player</th><th>Initial Status</th><th>Update 2 Status</th><th>Game Day Status</th></tr>
        <tr><td>10/10/26</td><td>Auburn</td><td>Final Receiver</td><td>Questionable</td><td>Doubtful</td><td>Out</td></tr>
        <tr><td>Sat, Oct 10, 2026</td><td>Texas</td><td>Updated Receiver</td><td>Questionable</td><td>Available</td><td></td></tr>
        <tr><td>bad date</td><td>Texas</td><td>Undated Receiver</td><td>Out</td><td></td><td>Out</td></tr>
        <tr><td>10/10/26</td><td>Texas</td><td>Exempt Receiver</td><td>Out</td><td></td><td>Exempt</td></tr></table>'''
    rows = parse_archive_document(html, conference="SEC", source_url="https://www.secsports.com/fbreports-archive")
    assert [(row["player_name"], row["status"], row["game_date"]) for row in rows] == [("Final Receiver", "Out", "2026-10-10"), ("Updated Receiver", "Available", "2026-10-10")]
    with pytest.raises(ConferenceReportUnavailable):
        parse_archive_document("<p>Report pending</p>", conference="SEC", source_url="https://www.secsports.com/fbreports")


def test_ambiguous_same_school_identity_never_assigns_an_injury(db_session):
    db_session.add_all([Player(name="Same Receiver", school="USC", position="WR"), Player(name="Same Receiver", school="USC", position="WR")]); db_session.commit()
    result = _upsert_official_availability_rows(db_session, season=2026, week=6, rows=[{"player_name": "Same Receiver", "team_name": "USC", "position": "WR", "conference": "BIG10", "status": "Out"}])
    assert result["skipped"] == 1
    assert db_session.query(Injury).count() == 0
    assert db_session.query(PlayerAvailabilityEvent).count() == 0


def test_current_grouped_report_cards_preserve_team_status_and_game_date():
    html = '''<h1>Games on October 17, 2026</h1><h2>Thursday Report</h2>
      <p>posted 7:10pm CT on Thursday, Oct. 15</p>
      <div><div><h3>Missouri</h3></div><div>
        <div><div>OUT</div><div><div>RB #29 Ahmad Hardy</div><div>TE #88 Gavin Hoffman</div></div></div>
        <div><div>DOUBTFUL</div><div><div>TE #87 Brett Norfleet</div></div></div>
        <div><div>PROBABLE</div><div><div>QB #13 Austin Simmons</div></div></div>
      </div></div>
      <div><div><h3>Ole Miss</h3></div><div><div>QUESTIONABLE</div><div>TE #80 Hayden Bradley</div></div></div>'''
    rows = parse_report_document(html, conference='SEC', source_url='https://www.secsports.com/fbreports')
    assert [(r['player_name'], r['team_name'], r['status']) for r in rows] == [
        ('Ahmad Hardy', 'Missouri', 'OUT'), ('Gavin Hoffman', 'Missouri', 'OUT'),
        ('Brett Norfleet', 'Missouri', 'DOUBTFUL'), ('Austin Simmons', 'Missouri', 'PROBABLE'),
        ('Hayden Bradley', 'Ole Miss', 'QUESTIONABLE'),
    ]
    assert all(r['game_date'] == '2026-10-17' for r in rows)
    assert rows[0]['position'] == 'RB'


def test_unscoped_cards_are_not_mistaken_for_an_official_report():
    import pytest
    html = '<h3>Missouri</h3><div>OUT<div>RB #29 Ahmad Hardy</div></div>'
    with pytest.raises(ConferenceReportUnavailable):
        parse_report_document(html, conference='SEC', source_url='https://www.secsports.com/fbreports')


def test_dated_report_only_updates_its_actual_game_week(db_session):
    from collegefootballfantasy_api.app.models.game import Game
    p = Player(name='Ahmad Hardy', school='Missouri', position='RB')
    db_session.add(p); db_session.flush()
    db_session.add(Game(season=2026, week=7, season_type='regular', external_id='official-date-fixture', home_team='Ole Miss', away_team='Missouri', start_date=datetime(2026,10,17,19,30,tzinfo=timezone.utc), schedule_status='scheduled'))
    db_session.flush()
    row = {'player_name':'Ahmad Hardy','team_name':'Missouri','position':'RB','status':'OUT','conference':'SEC','source_url':'https://www.secsports.com/fbreports','game_date':'2026-10-17'}
    result = _upsert_official_availability_rows(db_session, season=2026, week=7, rows=[row])
    assert result['created'] == 1
    assert db_session.query(Injury).filter_by(player_id=p.id,week=7).one().status == 'OUT'
    stale = {**row, 'status':'AVAILABLE', 'game_date':'2026-10-10'}
    result = _upsert_official_availability_rows(db_session, season=2026, week=7, rows=[stale])
    assert result['skipped'] == 1
    assert db_session.query(Injury).filter_by(player_id=p.id,week=7).one().status == 'OUT'


def test_acc_logo_identified_cards_do_not_mix_opposing_teams_or_statuses():
    html = '''<h1>Games of October 17, 2026</h1><img alt="ACC Football" />
      <div><div><img alt="Virginia" /></div><div>
        <div><div>OUT</div><div>RB #2 Peyton Lewis</div></div>
        <div><div>QUESTIONABLE</div><div>WR #5 Kameron Courtney</div></div>
      </div></div>
      <div><div><img alt="SMU" /></div><div><div>OUT</div><div>RB #4 Dramekco Green</div></div></div>
      <img alt="Network" />'''
    rows = parse_report_document(html, conference='ACC', source_url='https://theacc.com/sports/2025/8/28/availability-reporting-football.aspx')
    assert [(r['team_name'],r['player_name'],r['status']) for r in rows] == [
        ('Virginia','Peyton Lewis','OUT'), ('Virginia','Kameron Courtney','QUESTIONABLE'), ('SMU','Dramekco Green','OUT')]


def test_big_ten_split_rows_use_each_games_date_under_range_heading():
    html = '''<h1>Games of October 16 - October 17, 2026</h1>
    <section><img alt="B1G Football" /><div><img alt="Washington" />
      <div><div>Out</div><div><div>RB</div><div>#17</div><div>Jayden Limar</div></div></div>
    </div><div><img alt="Purdue" /><div><div>Questionable</div><div><div>TE</div><div>#16</div><div>Kylan Fox</div></div></div></div>
    <p>Friday, October 16 | 8:00 PM ET | West Lafayette, IN</p><img alt="Network" /></section>
    <section><div><img alt="Ohio State" /><div><div>Out</div><div><div>WR</div><div>#30</div><div>Amari Valerio-Hudson</div></div></div></div>
    <p>Saturday, October 17 | 12:00 PM ET | Bloomington, IN</p></section>'''
    rows = parse_report_document(html, conference='BIG10', source_url='https://bigten.org/fb/availability-reports/')
    assert [(r['team_name'], r['player_name'], r['status'], r['game_date']) for r in rows] == [
        ('Washington','Jayden Limar','OUT','2026-10-16'), ('Purdue','Kylan Fox','QUESTIONABLE','2026-10-16'),
        ('Ohio State','Amari Valerio-Hudson','OUT','2026-10-17')]


def test_big12_split_rows_keep_explicit_conference_date_without_guessing_logo_identity():
    html = '''<main><h1>Games on October 17, 2026</h1><img alt="Conference Logo" />
      <img alt="Team Logo" /><img alt="Team Logo" /><div><div>OUT</div>
      <div><div>WR</div><div>#22</div><div>Fletcher Fierro</div></div></div>
      <div><div>QUESTIONABLE</div><div><div>RB</div><div>#28</div><div>Jahiem White</div></div></div></main>'''
    rows = parse_report_document(html, conference='BIG12', source_url='https://big12sports.com/sports/2025/8/14/FBreporting.aspx')
    assert [(r['player_name'],r['position'],r['status'],r['team_name']) for r in rows] == [
        ('Fletcher Fierro','WR','OUT',None), ('Jahiem White','RB','QUESTIONABLE',None)]
    assert all(r['game_date']=='2026-10-17' for r in rows)


def test_big12_unlabelled_team_requires_unique_exact_conference_position_and_game_date(db_session):
    from collegefootballfantasy_api.app.models.game import Game
    players = [Player(name='Unique Receiver',school='TCU',position='WR'),
        Player(name='Same Receiver',school='TCU',position='WR'), Player(name='Same Receiver',school='Baylor',position='WR'),
        Player(name='Unique Receiver',school='Missouri',position='WR')]
    db_session.add_all(players)
    db_session.add(Game(season=2026,week=7,season_type='regular',external_id='b12-date-fixture',home_team='TCU',away_team='Baylor',start_date=datetime(2026,10,17,19,30,tzinfo=timezone.utc)))
    db_session.flush()
    row = {'player_name':'Unique Receiver','team_name':None,'position':'WR','status':'OUT','conference':'BIG12','game_date':'2026-10-17'}
    result = _upsert_official_availability_rows(db_session, season=2026,week=7,rows=[row])
    assert result['created']==1
    assert db_session.query(Injury).one().player_id==players[0].id
    for bad in ({**row,'player_name':'Same Receiver'}, {**row,'game_date':'2026-10-10'}, {**row,'position':'RB'}, {**row,'conference':'SEC'}, {**row,'game_date':None}):
        assert _upsert_official_availability_rows(db_session,season=2026,week=7,rows=[bad])['skipped']==1
    assert db_session.query(Injury).count()==1


def test_big_ten_embedded_link_unwraps_only_the_explicit_public_report_destination():
    html = '<iframe id="embedded-app" src="https://nam04.safelinks.protection.outlook.com/?url=https%3A%2F%2Fapp.hdintelligence.com%2F%3Fsource%3DB10%26sport%3DFootball%26conf%3DB10%26type%3Dreport"></iframe>'
    assert _embedded_report_url(BeautifulSoup(html,'html.parser'),'https://bigten.org/fb/availability-reports/') == 'https://app.hdintelligence.com/?source=B10&sport=Football&conf=B10&type=report'
