from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll
from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_games_by_school, school_key
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.league_roster_matchup import _live_game_context_by_player, _serialize_team_roster, build_matchup_tab_view
from tests.api.scoring_helpers import create_scoring_fixture


def game(external_id, *, opponent="UCLA", status="final", season=2026):
    return Game(external_id=external_id, season=season, week=1, season_type="regular",
                home_team="California", away_team=opponent, schedule_status=status,
                start_date=datetime(2026, 9, 5, tzinfo=timezone.utc))


@pytest.mark.parametrize("reverse", [False, True])
def test_exact_sheet_placeholder_does_not_hide_provider_game(db_session, reverse):
    final, placeholder = game("401858210"), game("sheet-2026-w1-california-vs-ucla", status=None)
    games = [final, placeholder]
    selected = fantasy_games_by_school(db_session, season=2026, week=1, games=games[::-1] if reverse else games)
    assert selected[school_key("California")] is final
    assert selected[school_key("UCLA")] is final
    assert placeholder.schedule_status is None


@pytest.mark.parametrize("other", [game("401999999"), game("sheet-other", opponent="Stanford")])
def test_real_conflicts_remain_ambiguous(db_session, other):
    selected = fantasy_games_by_school(db_session, season=2026, week=1, games=[game("401858210"), other])
    assert selected[school_key("California")] is None


def test_placeholder_without_same_season_provider_is_preserved(db_session):
    placeholder = game("sheet-only", status=None)
    selected = fantasy_games_by_school(db_session, season=2026, week=1,
                                      games=[placeholder, game("401858210", season=2025)])
    assert selected[school_key("California")] is placeholder


@pytest.mark.parametrize("has_stale_poll", [False, True])
def test_final_game_without_player_stats_stays_final(db_session, has_stale_poll):
    db_session.add_all([game("401858210"), game("sheet-2026-w1-california-vs-ucla", status=None)])
    if has_stale_poll:
        db_session.add(ProviderGamePoll(provider="espn", provider_game_id="401858210", season=2026,
            week=1, status="live", accepted_snapshot_hash="old",
            latest_payload={"header": {"competitions": [{"status": {"type": {"state": "in"}}}]}}))
    db_session.flush()
    contexts = _live_game_context_by_player(db_session, season=2026, week=1,
                                           player_schools={1301: "California"})
    assert contexts[1301].state == "final"
    assert contexts[1301].player_stats is None


@pytest.mark.parametrize("matchup_view", [False, True])
def test_zero_stat_roster_row_is_final_without_changing_scores(db_session, matchup_view):
    league, home, _away, players, matchup = create_scoring_fixture(db_session)
    user = User(first_name="Final", email="zero-final@example.com", password_hash="hash", api_token="zero-final")
    db_session.add(user)
    db_session.flush()
    home.owner_user_id = user.id
    players["bench"].school = "California"
    db_session.add_all([game("401858210"), game("sheet-2026-w1-california-vs-ucla", status=None)])
    db_session.commit()
    before = (matchup.home_score, matchup.away_score, matchup.status)
    rows = build_matchup_tab_view(db_session, league, user, selected_week=1).my_roster if matchup_view else _serialize_team_roster(db_session, league, home, 1)
    row = next(row for row in rows if row.player_id == players["bench"].id)
    assert row.live_game_state == "final"
    assert row.current_fantasy_points is None  # no invented counting stats
    assert row.final_game_stat_line is None
    assert (matchup.home_score, matchup.away_score, matchup.status) == before
