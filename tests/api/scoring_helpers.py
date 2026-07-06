from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team


def create_scoring_fixture(db_session, scoring_json=None):
    league = League(name="Scoring League", season_year=2026, max_teams=2, status="post_draft")
    db_session.add(league)
    db_session.flush()
    settings = LeagueSettings(
        league_id=league.id,
        scoring_json=scoring_json or {"ppr": 1},
        roster_slots_json={"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "BENCH": 2, "IR": 1},
        playoff_teams=2,
        waiver_type="faab",
        trade_review_type="commissioner",
        superflex_enabled=False,
        kicker_enabled=True,
        defense_enabled=False,
    )
    home = Team(league_id=league.id, name="Home Team")
    away = Team(league_id=league.id, name="Away Team")
    db_session.add_all([settings, home, away])
    db_session.flush()
    players = {
        "qb": Player(name="Test QB", position="QB", school="Test", external_id="101"),
        "rb": Player(name="Test RB", position="RB", school="Test", external_id="102"),
        "wr": Player(name="Test WR", position="WR", school="Test", external_id="103"),
        "bench": Player(name="Bench WR", position="WR", school="Test", external_id="104"),
        "ir": Player(name="IR RB", position="RB", school="Test", external_id="105"),
        "away_qb": Player(name="Away QB", position="QB", school="Test", external_id="106"),
        "available": Player(name="Available WR", position="WR", school="Test", external_id="107"),
    }
    db_session.add_all(players.values())
    db_session.flush()
    db_session.add_all(
        [
            RosterEntry(league_id=league.id, team_id=home.id, player_id=players["qb"].id, slot="QB", status="active"),
            RosterEntry(league_id=league.id, team_id=home.id, player_id=players["rb"].id, slot="RB", status="active"),
            RosterEntry(league_id=league.id, team_id=home.id, player_id=players["wr"].id, slot="WR", status="active"),
            RosterEntry(league_id=league.id, team_id=home.id, player_id=players["bench"].id, slot="BENCH", status="active"),
            RosterEntry(league_id=league.id, team_id=home.id, player_id=players["ir"].id, slot="IR", status="active"),
            RosterEntry(league_id=league.id, team_id=away.id, player_id=players["away_qb"].id, slot="QB", status="active"),
        ]
    )
    db_session.add_all(
        [
            PlayerStat(player_id=players["qb"].id, season=2026, week=1, source="sportsdata", stats={"PassingYards": 250, "PassingTouchdowns": 2, "Interceptions": 1}),
            PlayerStat(player_id=players["rb"].id, season=2026, week=1, source="sportsdata", stats={"RushingYards": 80, "RushingTouchdowns": 1, "Receptions": 3, "ReceivingYards": 20}),
            PlayerStat(player_id=players["wr"].id, season=2026, week=1, source="sportsdata", stats={"Receptions": 5, "ReceivingYards": 100, "ReceivingTouchdowns": 1}),
            PlayerStat(player_id=players["bench"].id, season=2026, week=1, source="sportsdata", stats={"Receptions": 10, "ReceivingYards": 100, "ReceivingTouchdowns": 2}),
            PlayerStat(player_id=players["ir"].id, season=2026, week=1, source="sportsdata", stats={"RushingYards": 200, "RushingTouchdowns": 3}),
            PlayerStat(player_id=players["away_qb"].id, season=2026, week=1, source="sportsdata", stats={"PassingYards": 100}),
        ]
    )
    matchup = Matchup(
        league_id=league.id,
        season=2026,
        week=1,
        home_team_id=home.id,
        away_team_id=away.id,
        status="scheduled",
    )
    db_session.add(matchup)
    db_session.commit()
    return league, home, away, players, matchup
