from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from scripts.import_espn_live_identities import (
    CachedESPNReference,
    RateLimitPaused,
    apply_verified_player_mappings,
    apply_verified_schedule,
    flatten_roster,
    normalize_exact_name,
    plan_player_identities,
    plan_schedule,
)


def _player(name: str, school: str = "Ohio State", position: str = "WR") -> Player:
    return Player(
        name=name,
        school=school,
        position=position,
        sheet_source_sheet_id="canonical-preseason:2026:test",
        sheet_projected_season_points=100,
    )


def _roster_payload() -> dict:
    return {
        "athletes": [
            {
                "items": [
                    {
                        "id": "101",
                        "displayName": "Chris Henry Jr",
                        "college": {"id": "194", "name": "Ohio State"},
                        "position": {"abbreviation": "WR"},
                    },
                    {
                        "id": "102",
                        "displayName": "Same Name",
                        "college": {"id": "194", "name": "Ohio State"},
                        "position": {"abbreviation": "WR"},
                    },
                    {
                        "id": "103",
                        "displayName": "Same Name",
                        "college": {"id": "194", "name": "Ohio State"},
                        "position": {"abbreviation": "WR"},
                    },
                ]
            }
        ]
    }


def _profile(player_id: str) -> dict:
    names = {"101": "Chris Henry Jr.", "102": "Same Name", "103": "Same Name"}
    return {
        "athlete": {
            "id": player_id,
            "displayName": names[player_id],
            "team": {"location": "Ohio State"},
            "position": {"abbreviation": "WR"},
        }
    }


def test_identity_planner_verifies_only_exact_roster_and_profile_matches(db_session):
    exact = _player("Chris Henry Jr.")
    collision = _player("Same Name")
    missing = _player("Missing Player")
    db_session.add_all([exact, collision, missing])
    db_session.flush()

    records = plan_player_identities(
        [exact, collision, missing],
        flatten_roster(_roster_payload()),
        _profile,
        {},
    )

    by_player = {record["internal_player_id"]: record for record in records}
    assert normalize_exact_name("Chris Henry Jr.") == normalize_exact_name("Chris Henry Jr")
    assert by_player[exact.id]["status"] == "verified"
    assert by_player[exact.id]["espn_player_id"] == "101"
    assert by_player[exact.id]["source_snapshot_hash"]
    assert by_player[collision.id]["status"] == "needs_review"
    assert by_player[collision.id]["reason"] == "multiple_exact_roster_candidates"
    assert by_player[missing.id]["status"] == "unresolved"
    assert by_player[missing.id]["reason"] == "missing_exact_roster_candidate"

    assert apply_verified_player_mappings(db_session, records) == 1
    db_session.commit()
    mapping = db_session.query(PlayerProviderId).filter_by(player_id=exact.id, provider="espn").one()
    assert mapping.provider_player_id == "101"
    assert mapping.verification_status == "verified"
    assert apply_verified_player_mappings(db_session, records) == 0


def test_identity_planner_marks_an_unavailable_profile_for_review_instead_of_guessing(db_session):
    player = _player("Chris Henry Jr.")
    db_session.add(player)
    db_session.flush()

    records = plan_player_identities(
        [player],
        flatten_roster(_roster_payload()),
        lambda _player_id: {"_reference_error": "HTTP 404"},
        {},
    )

    assert records[0]["status"] == "needs_review"
    assert records[0]["reason"] == "profile_reference_unavailable"
    assert records[0]["reference_error"] == "HTTP 404"


def test_identity_planner_uses_canonical_rank_only_for_review_order(db_session):
    player = _player("Missing Player")
    player.cfb27_rank = 7
    db_session.add(player)
    db_session.flush()

    records = plan_player_identities([player], [], _profile, {})

    assert records[0]["status"] == "unresolved"
    assert records[0]["review_priority"] == "P0"


def test_reference_cache_refetches_a_partial_entry_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.import_espn_live_identities.time.sleep", lambda _delay: None)
    reference = CachedESPNReference(object(), tmp_path, delay_seconds=0.2)
    path = reference._path("profiles", "101")
    path.parent.mkdir(parents=True)
    path.write_text("{", encoding="utf-8")

    assert reference._load_or_fetch("profiles", "101", lambda: {"athlete": {"id": "101"}}) == {"athlete": {"id": "101"}}
    assert path.with_suffix(".tmp").exists() is False
    metadata = reference._metadata_path("profiles", "101")
    assert metadata.is_file()
    assert '"http_status": 200' in metadata.read_text(encoding="utf-8")


def test_reference_cache_persists_rate_limit_checkpoint(tmp_path):
    reference = CachedESPNReference(object(), tmp_path, delay_seconds=0.2)

    with pytest.raises(RateLimitPaused):
        reference._record_rate_limit("60")

    checkpoint = reference._rate_limit_path()
    assert checkpoint.is_file()
    with pytest.raises(RateLimitPaused):
        reference._assert_not_rate_limited()


def test_schedule_planner_requires_event_participants_and_kickoff_then_applies_idempotently(db_session):
    event = {
        "id": "401999001",
        "date": "2026-08-29T17:00:00Z",
        "status": {"type": {"state": "pre"}},
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "home", "team": {"id": "194", "location": "Ohio State"}},
                    {"homeAway": "away", "team": {"id": "251", "location": "Texas"}},
                ]
            }
        ],
    }
    records, review = plan_schedule(
        [event], season=2026, weeks=[1], internal_schools={"Ohio State", "Texas"}
    )
    assert review == []
    assert records[0]["espn_event_id"] == "401999001"
    assert records[0]["kickoff"] == datetime(2026, 8, 29, 17, tzinfo=timezone.utc).isoformat()

    assert apply_verified_schedule(db_session, records) == 1
    db_session.commit()
    assert db_session.query(Game).filter_by(external_id="401999001").count() == 1
    assert db_session.query(TeamSchedule).filter_by(season=2026, week=1).count() == 2
    assert apply_verified_schedule(db_session, records) == 0
    db_session.commit()
    assert db_session.query(Game).filter_by(external_id="401999001").count() == 1
