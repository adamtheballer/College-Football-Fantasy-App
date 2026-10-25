import argparse
import json

import pytest

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.models.player_news_event import PlayerNewsEvent


def test_verified_bye_absence_does_not_require_or_invent_a_projection(db_session, monkeypatch):
    from conftest import TestingSessionLocal
    from scripts import apply_injury_projection_correction as correction
    monkeypatch.setattr(correction,"SessionLocal",TestingSessionLocal)
    p=Player(name="Bye Week QB",school="Ohio State",position="QB")
    db_session.add(p);db_session.commit()
    args=argparse.Namespace(season=2026,week=8,player=p.name,school=p.school,status="OUT",
        injury="Arm",return_timeline="Out indefinitely",notes="Coach confirmed absence",
        source_url=["https://example.test/one","https://example.test/two"],
        require_corroboration=True,effective_until_week=11,apply=True)
    result=correction.apply_correction(args)
    assert result["fantasy_points"] is None
    assert db_session.query(Injury).one().status == "OUT"
    assert db_session.query(PlayerAvailabilityEvent).one().reviewed is True


def test_manifest_is_seeded_once_and_later_return_is_never_replayed(db_session, monkeypatch, tmp_path):
    from conftest import TestingSessionLocal
    from scripts import sync_reviewed_availability as job
    from scripts import apply_injury_projection_correction as correction
    monkeypatch.setattr(job,"SessionLocal",TestingSessionLocal)
    monkeypatch.setattr(correction,"SessionLocal",TestingSessionLocal)
    p=Player(name="Julian Sayin",school="Ohio State",position="QB")
    db_session.add(p);db_session.commit()
    record=json.loads(job.MANIFEST.read_text())[0]
    manifest=tmp_path/'reports.json';manifest.write_text(json.dumps([record]))
    monkeypatch.setattr(job,"MANIFEST",manifest)
    assert job.sync_reviewed_reports(season=2026,week=8)["seeded"] == 1
    assert job.sync_reviewed_reports(season=2026,week=8)["seeded"] == 0
    assert db_session.query(PlayerNewsEvent).count() == 1
    assert db_session.query(PlayerAvailabilityEvent).count() == 1
    db_session.add(Injury(player_id=p.id,season=2026,week=9,status="FULL"));db_session.commit()
    assert job.sync_reviewed_reports(season=2026,week=9)["seeded"] == 0
    assert db_session.query(Injury).filter_by(week=9).one().status == "FULL"


@pytest.mark.parametrize("status,probability", [("FULL", 1.0), ("TBD", 0.7), ("PROBABLE", 1.0)])
def test_reviewed_designation_uses_domain_probability_without_inventing_practice(db_session, monkeypatch, status, probability):
    from conftest import TestingSessionLocal
    from scripts import apply_injury_projection_correction as correction
    monkeypatch.setattr(correction, "SessionLocal", TestingSessionLocal)
    player = Player(name="Reviewed return", school="LSU", position="TE")
    db_session.add(player)
    db_session.commit()
    args = correction.parse_args([
        "--season", "2026", "--week", "8", "--player", player.name, "--school", player.school,
        "--status", status, "--injury", "Shoulder", "--return-timeline", "Reviewed update",
        "--notes", "Reported game designation", "--source-url", "https://example.test/team", "--apply",
    ])
    correction.apply_correction(args)
    injury = db_session.query(Injury).one()
    event = db_session.query(PlayerAvailabilityEvent).one()
    assert injury.status == event.status == status
    assert injury.practice_level is None
    assert injury.is_returning is (status == "FULL")
    assert (event.probability_active, event.availability_multiplier) == (probability, probability)


def test_audit_manifest_seeds_exact_identity_and_explicit_return_once(db_session, monkeypatch, tmp_path):
    from conftest import TestingSessionLocal
    from scripts import sync_reviewed_availability as job
    from scripts import apply_injury_projection_correction as correction
    monkeypatch.setattr(job, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(correction, "SessionLocal", TestingSessionLocal)
    records = json.loads(job.MANIFEST.read_text())[5:]
    players = [Player(name=r["player"], school=r["school"], position=r["position"]) for r in records]
    other = Player(name="Jordan Washington", school="North Carolina", position="TE")
    db_session.add_all([*players, other])
    db_session.flush()
    green = next(p for p in players if p.name == "Trey'Dez Green")
    db_session.add(Injury(player_id=green.id, season=2026, week=7, status="OUT"))
    db_session.commit()
    manifest = tmp_path / "audit.json"
    manifest.write_text(json.dumps(records))
    monkeypatch.setattr(job, "MANIFEST", manifest)
    result = job.sync_reviewed_reports(season=2026, week=8)
    assert result["seeded"] == len(records)
    assert result["correction_errors"] == []
    assert job.sync_reviewed_reports(season=2026, week=8)["seeded"] == 0
    assert db_session.query(Injury).filter_by(player_id=other.id).count() == 0
    assert db_session.query(Injury).filter_by(player_id=green.id, week=8).one().status == "FULL"
    assert db_session.query(PlayerAvailabilityEvent).count() == len(records)
    assert db_session.query(PlayerNewsEvent).count() == len(records)
