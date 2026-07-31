from types import SimpleNamespace

from scripts.audit_canonical_player_registry import audit_canonical_player_registry


def _identity(name: str = "Jeremiah Smith") -> dict[str, str]:
    return {"NAME": name, "SCHOOL": "Ohio State", "POSITION": "WR"}


def _projection(name: str = "Jeremiah Smith") -> dict[str, str]:
    return {"PLAYER": name, "TEAM": "Ohio State", "POSITION": "WR"}


def _player(*, player_id: int | None = 41, name: str = "Jeremiah Smith", source: str | None = None):
    return SimpleNamespace(
        id=player_id,
        name=name,
        school="Ohio State",
        position="WR",
        sheet_source_sheet_id=source,
    )


def test_registry_audit_accepts_an_app_owned_canonical_id_without_a_source_id_column():
    report = audit_canonical_player_registry(
        identity_rows=[_identity()],
        projection_rows=[_projection()],
        players=[_player()],
    )

    assert report["status"] == "PASS"
    assert report["canonical_id_owner"] == "application database players.id"
    assert report["source_canonical_id_column_required"] is False
    assert report["mapped_internal_player_count"] == 1


def test_registry_audit_rejects_source_rows_that_do_not_resolve_to_one_player():
    report = audit_canonical_player_registry(
        identity_rows=[_identity()],
        projection_rows=[_projection()],
        players=[_player(player_id=41), _player(player_id=42)],
    )

    assert report["status"] == "FAIL"
    assert report["source_keys_with_multiple_internal_players_count"] == 1
    assert report["source_keys_with_multiple_internal_players"][0]["player_ids"] == [41, 42]


def test_registry_audit_rejects_a_bootstrap_player_left_out_of_the_approved_snapshot():
    report = audit_canonical_player_registry(
        identity_rows=[_identity()],
        projection_rows=[_projection()],
        players=[
            _player(),
            _player(
                player_id=42,
                name="Stale Player",
                source="canonical-preseason:2026:SEC",
            ),
        ],
    )

    assert report["status"] == "FAIL"
    assert report["bootstrap_players_absent_from_approved_snapshot_count"] == 1


