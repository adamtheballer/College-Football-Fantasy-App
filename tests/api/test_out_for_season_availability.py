from collegefootballfantasy_api.app.crud.player import list_players
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.injury_status import is_out_for_season


def test_season_ending_injury_removes_player_from_acquisition_pool_but_keeps_audit_projection(db_session):
    player = Player(
        name="Season Ending Receiver",
        school="South Carolina",
        position="WR",
        sheet_source_sheet_id="canonical-preseason:2026:verified",
        sheet_projected_season_points=196.8,
    )
    db_session.add(player)
    db_session.flush()
    db_session.add(
        Injury(
            player_id=player.id,
            season=2026,
            week=3,
            status="OUT_FOR_SEASON",
            return_timeline="Out for season",
        )
    )
    db_session.commit()

    players, _ = list_players(
        db_session,
        limit=100,
        offset=0,
        position=None,
        school=None,
        search=None,
        draft_eligible=True,
    )

    assert player.sheet_projected_season_points == 196.8
    assert is_out_for_season(db_session, player_id=player.id, season=2026)
    assert player.id not in {candidate.id for candidate in players}


def test_player_card_keeps_season_ending_status_after_the_week_that_reported_it(client, db_session):
    player = Player(name="Season Ending Card", position="RB", school="Texas")
    db_session.add(player)
    db_session.flush()
    db_session.add(Injury(player_id=player.id, season=2026, week=3, status="OUT_FOR_SEASON"))
    db_session.commit()

    response = client.get(f"/players/{player.id}/card?injury_season=2026&injury_week=4")

    assert response.status_code == 200
    assert response.json()["current_injury_status"] == "OUT_FOR_SEASON"
