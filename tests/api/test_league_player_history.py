from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.league_player_history import (
    EVENT_DRAFTED,
    append_league_player_event,
)
from collegefootballfantasy_api.app.core.security import create_access_token


def _headers(user: User) -> dict[str, str]:
    token, _ = create_access_token(user_id=user.id, email=user.email)
    return {"Authorization": f"Bearer {token}"}


def _seed(db_session):
    user = User(email="history@example.com", first_name="History", password_hash="x", api_token="history-token")
    db_session.add(user); db_session.flush()
    league = League(name="History League", commissioner_user_id=user.id, season_year=2026, max_teams=2, status="post_draft")
    db_session.add(league); db_session.flush()
    db_session.add(LeagueMember(league_id=league.id, user_id=user.id, role="commissioner"))
    team = Team(league_id=league.id, name="History Team", owner_user_id=user.id, owner_name="History")
    player = Player(name="Ledger Player", position="RB", school="Texas", sheet_projected_season_points=222.2)
    db_session.add_all([team, player]); db_session.commit()
    return user, league, team, player


def test_history_is_league_scoped_idempotent_and_authorized(client, db_session):
    user, league, team, player = _seed(db_session)
    append_league_player_event(
        db_session, league=league, player=player, event_type=EVENT_DRAFTED,
        event_key="draft-pick:history-test", occurred_at=datetime.now(timezone.utc),
        fantasy_team=team, to_team=team, manager=user, metadata={"overall_pick": 1},
    )
    # The same worker/backfill retry must not add a duplicate timeline event.
    append_league_player_event(
        db_session, league=league, player=player, event_type=EVENT_DRAFTED,
        event_key="draft-pick:history-test", fantasy_team=team, to_team=team, manager=user,
    )
    db_session.commit()

    response = client.get(f"/leagues/{league.id}/players/{player.id}/history", headers=_headers(user))
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["events"][0]["event_type"] == "DRAFTED"
    assert payload["events"][0]["player_value_at_event"] == 222.2
    assert payload["events"][0]["to_team"]["name"] == "History Team"

    stranger = User(email="stranger@example.com", first_name="Stranger", password_hash="x", api_token="stranger-token")
    db_session.add(stranger); db_session.commit()
    forbidden = client.get(f"/leagues/{league.id}/players/{player.id}/history", headers=_headers(stranger))
    assert forbidden.status_code == 403
    missing = client.get(f"/leagues/{league.id}/players/999999/history", headers=_headers(user))
    assert missing.status_code == 404


def test_history_backfills_legacy_draft_pick_with_selection_details(client, db_session):
    user, league, team, player = _seed(db_session)
    draft = Draft(league_id=league.id, draft_datetime_utc=datetime.now(timezone.utc), status="completed")
    db_session.add(draft); db_session.flush()
    db_session.add(
        DraftPick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=player.id,
            made_by_user_id=user.id,
            round_number=4,
            round_pick=4,
            overall_pick=16,
            auto_pick=True,
        )
    )
    db_session.commit()

    response = client.get(f"/leagues/{league.id}/players/{player.id}/history", headers=_headers(user))
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["events"][0]["event_type"] == "AUTO_DRAFTED"
    assert payload["events"][0]["to_team"]["name"] == "History Team"
    assert payload["events"][0]["metadata"] == {
        "round": 4, "pick_in_round": 4, "overall_pick": 16, "auto_pick": True, "legacy_backfill": True,
    }
