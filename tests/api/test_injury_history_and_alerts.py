from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.injury import Injury, InjuryHistory
from collegefootballfantasy_api.app.models.injury_impact import InjuryImpact
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.watchlist import Watchlist, WatchlistPlayer
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.sportsdata_sync import _upsert_power4_injuries


def test_injury_sync_preserves_history_and_marks_cleared(client, db_session):
    player = Player(name="History Injury RB", position="RB", school="Alabama", external_id="sd-hist-1")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        WeeklyProjection(
            player_id=player.id,
            season=2026,
            week=1,
            fantasy_points=20.0,
        )
    )
    db_session.flush()

    changes = _upsert_power4_injuries(
        db_session,
        season=2026,
        week=1,
        conference="SEC",
        rows=[
            {
                "player_name": player.name,
                "team_name": "Alabama",
                "position": "RB",
                "status": "QUESTIONABLE",
                "normalized_status": "questionable",
                "injury": "Ankle",
                "body_part": "Ankle",
                "return_timeline": "Day-to-day",
                "practice_level": "Limited",
                "notes": "Limited at practice",
                "external_id": player.external_id,
                "source": "sportsdata",
                "source_updated_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
            }
        ],
    )
    db_session.flush()

    assert changes["created"] == 1
    injury = db_session.query(Injury).filter(Injury.player_id == player.id).one()
    assert injury.status == "QUESTIONABLE"
    assert injury.normalized_status == "questionable"
    assert injury.body_part == "Ankle"
    assert injury.source == "sportsdata"
    assert injury.first_seen_at is not None
    assert injury.last_seen_at is not None
    assert injury.cleared_at is None

    history = db_session.query(InjuryHistory).filter(InjuryHistory.player_id == player.id).all()
    assert len(history) == 1
    assert history[0].status == "QUESTIONABLE"

    impact = db_session.query(InjuryImpact).filter(InjuryImpact.player_id == player.id).one()
    assert impact.delta_fpts == -6.0
    assert impact.multiplier == 0.7
    assert "questionable" in (impact.reason or "")

    cleared = _upsert_power4_injuries(
        db_session,
        season=2026,
        week=1,
        conference="SEC",
        rows=[],
    )
    db_session.flush()

    assert cleared["cleared"] == 1
    injury = db_session.query(Injury).filter(Injury.player_id == player.id).one()
    assert injury.status == "HEALTHY"
    assert injury.normalized_status == "healthy"
    assert injury.cleared_at is not None
    assert db_session.query(InjuryHistory).filter(InjuryHistory.player_id == player.id).count() == 2


def test_rostered_player_gets_injury_notification(client, db_session):
    user = User(
        email="injury-owner@example.com",
        username="injury-owner",
        first_name="Injury",
        password_hash="hash",
        api_token="injury-owner-token",
    )
    league = League(name="Injury League", commissioner_user_id=None, season_year=2026, max_teams=2)
    player = Player(name="Rostered Injury QB", position="QB", school="Alabama", external_id="sd-alert-1")
    db_session.add_all([user, league, player])
    db_session.flush()
    league.commissioner_user_id = user.id
    team = Team(league_id=league.id, name="Alert Team", owner_user_id=user.id)
    db_session.add(team)
    db_session.flush()
    db_session.add(RosterEntry(league_id=league.id, team_id=team.id, player_id=player.id, slot="QB", status="active"))
    db_session.flush()

    _upsert_power4_injuries(
        db_session,
        season=2026,
        week=1,
        conference="SEC",
        rows=[
            {
                "player_name": player.name,
                "team_name": "Alabama",
                "position": "QB",
                "status": "OUT",
                "normalized_status": "out",
                "injury": "Shoulder",
                "body_part": "Shoulder",
                "return_timeline": "TBD",
                "practice_level": "DNP",
                "notes": "Ruled out",
                "external_id": player.external_id,
                "source": "sportsdata",
                "source_updated_at": None,
            }
        ],
    )
    db_session.flush()

    notification = db_session.query(NotificationLog).filter(NotificationLog.user_id == user.id).one()
    assert notification.alert_type == "lineup_lock_warning"
    assert notification.league_id == league.id
    assert notification.source_entity_type == "injury"
    assert notification.payload["player_id"] == player.id
    assert notification.payload["new_status"] == "OUT"


def test_watchlist_injury_alert_respects_item_preference(client, db_session):
    user = User(
        email="watch-injury@example.com",
        username="watch-injury",
        first_name="Watch",
        password_hash="hash",
        api_token="watch-injury-token",
    )
    league = League(name="Watch Injury League", commissioner_user_id=None, season_year=2026, max_teams=2)
    player = Player(name="Watch Injury WR", position="WR", school="Alabama", external_id="sd-watch-alert-1")
    db_session.add_all([user, league, player])
    db_session.flush()
    league.commissioner_user_id = user.id
    watchlist = Watchlist(user_id=user.id, league_id=league.id, name="Muted Injury Targets")
    db_session.add(watchlist)
    db_session.flush()
    db_session.add(
        WatchlistPlayer(
            watchlist_id=watchlist.id,
            player_id=player.id,
            priority=1,
            tags=["injury-watch"],
            alert_injury=False,
        )
    )
    db_session.flush()

    _upsert_power4_injuries(
        db_session,
        season=2026,
        week=1,
        conference="SEC",
        rows=[
            {
                "player_name": player.name,
                "team_name": "Alabama",
                "position": "WR",
                "status": "QUESTIONABLE",
                "normalized_status": "questionable",
                "injury": "Hamstring",
                "body_part": "Hamstring",
                "return_timeline": "Day-to-day",
                "practice_level": "Limited",
                "notes": "Limited",
                "external_id": player.external_id,
                "source": "sportsdata",
                "source_updated_at": None,
            }
        ],
    )
    db_session.flush()

    assert db_session.query(NotificationLog).filter(NotificationLog.user_id == user.id).count() == 0
