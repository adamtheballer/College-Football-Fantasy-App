from sqlalchemy import event

from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.league_roster_matchup import build_matchup_tab_view
from tests.api.scoring_helpers import create_scoring_fixture


def test_matchup_tab_uses_a_bounded_number_of_selects(client, db_session):
    league, home, away, _players, _matchup = create_scoring_fixture(db_session)
    user = User(
        first_name="Performance",
        email="performance@example.com",
        password_hash="hash",
        api_token="performance-token",
    )
    db_session.add(user)
    db_session.flush()
    home.owner_user_id = user.id
    db_session.add_all(
        [
            Standing(league_id=league.id, team_id=home.id, season=2026, week=1, wins=1, losses=0, ties=0),
            Standing(league_id=league.id, team_id=away.id, season=2026, week=1, wins=0, losses=1, ties=0),
        ]
    )
    db_session.commit()
    db_session.expire_all()
    db_session.refresh(league)
    db_session.refresh(user)

    select_count = 0

    def count_selects(_connection, _cursor, statement, _parameters, _context, _executemany):
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    event.listen(db_session.bind, "before_cursor_execute", count_selects)
    try:
        response = build_matchup_tab_view(db_session, league, user, selected_week=1)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", count_selects)

    assert response.my_team is not None
    assert response.opponent_team is not None
    assert len(response.my_roster) == 8
    assert len(response.opponent_roster) == 8
    assert select_count <= 8
