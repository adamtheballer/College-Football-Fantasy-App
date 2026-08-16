from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from scripts.import_espn_live_identities import (
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
    assert apply_verified_schedule(db_session, records) == 1
    db_session.commit()
    assert db_session.query(Game).filter_by(external_id="401999001").count() == 1
