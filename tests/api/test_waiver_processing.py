from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.services.league_roster_matchup import build_waivers_view
from collegefootballfantasy_api.app.services.waiver_service import process_waiver_claims_once


def test_due_waiver_processing_is_idempotent_with_league_serialization(client, db_session):
    user = User(
        email="waiver-owner@example.com",
        first_name="Waiver",
        password_hash="test",
        api_token="waiver-owner-token",
    )
    db_session.add(user)
    db_session.flush()
    league = League(name="Waiver Lifecycle League", season_year=2026, commissioner_user_id=user.id, max_teams=1)
    db_session.add(league)
    db_session.flush()
    db_session.add(
        LeagueSettings(
            league_id=league.id,
            roster_slots_json={"QB": 1},
            waiver_type="faab",
            waiver_period_hours=24,
        )
    )
    team = Team(league_id=league.id, name="Waiver Team", owner_user_id=user.id, owner_name="Waiver")
    player = Player(name="Waiver Available QB", position="QB", school="Texas")
    db_session.add_all([team, player])
    db_session.flush()
    claim = WaiverClaim(
        league_id=league.id,
        team_id=team.id,
        add_player_id=player.id,
        created_by_user_id=user.id,
        status="pending",
        priority_snapshot=1,
        faab_bid=7,
        process_after=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(claim)
    db_session.commit()

    assert process_waiver_claims_once(db_session) == {"processed": 1, "failed": 0, "pending": 0}
    assert process_waiver_claims_once(db_session) == {"processed": 0, "failed": 0, "pending": 0}
    assert db_session.query(RosterEntry).filter_by(league_id=league.id, player_id=player.id).count() == 1
    assert db_session.query(WaiverPriority).filter_by(league_id=league.id, team_id=team.id).one().faab_spent == 7

    waiver_view = build_waivers_view(db_session, league, user)
    assert waiver_view.waiver_priority == 1
    assert waiver_view.faab_remaining == 93
    assert waiver_view.waiver_rules["faab_budget"] == 100
