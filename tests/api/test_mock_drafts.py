import pytest

from collegefootballfantasy_api.app.models.mock_draft import MockDraft
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.mock_draft_service import (
    MockDraftConflict,
    auto_pick_mock_draft,
    make_mock_pick,
)


def test_backend_mock_draft_api_is_not_active(client):
    response = client.post(
        "/mock-drafts",
        json={"title": "Practice Room", "league_size": 4, "rounds": 2},
    )

    assert response.status_code == 404


def test_mock_draft_manual_and_auto_picks_use_only_the_canonical_snapshot(db_session):
    user = User(
        email="mock-canonical-owner@example.com",
        first_name="Mock",
        password_hash="test",
        api_token="mock-canonical-owner-token",
    )
    canonical = Player(
        name="Reviewed Mock QB",
        position="QB",
        school="Texas",
        sheet_adp=1,
        sheet_source_sheet_id="canonical-preseason:2026:test-fixture",
        sheet_projected_season_points=200.0,
    )
    legacy = Player(
        name="Legacy Mock QB",
        position="QB",
        school="Texas",
        sheet_adp=0,
        sheet_source_sheet_id="provider-sync:2026:legacy",
        sheet_projected_season_points=999.0,
    )
    db_session.add_all((user, canonical, legacy))
    db_session.flush()
    mock_draft = MockDraft(owner_user_id=user.id, league_size=2, rounds=1, current_pick=1, status="active")
    db_session.add(mock_draft)
    db_session.commit()

    with pytest.raises(MockDraftConflict, match="approved mock draft pool"):
        make_mock_pick(db_session, mock_draft.id, user.id, legacy.id)

    result = auto_pick_mock_draft(db_session, mock_draft.id, user.id)
    assert [pick.player_id for pick in result.picks] == [canonical.id]
