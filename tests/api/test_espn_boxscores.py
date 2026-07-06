from collegefootballfantasy_api.app.integrations.espn import extract_player_box_score_stats
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.espn_stats_sync import upsert_espn_weekly_player_stats
from collegefootballfantasy_api.app.services.scoring_service import calculate_player_fantasy_points, normalize_player_stats


def espn_summary_payload():
    return {
        "event_id": "401",
        "boxscore": {
            "players": [
                {
                    "team": {
                        "location": "Texas",
                        "displayName": "Texas Longhorns",
                        "shortDisplayName": "Texas",
                        "abbreviation": "TEX",
                    },
                    "statistics": [
                        {
                            "name": "passing",
                            "keys": [
                                "completions/passingAttempts",
                                "passingYards",
                                "yardsPerPassAttempt",
                                "passingTouchdowns",
                                "interceptions",
                            ],
                            "athletes": [
                                {
                                    "athlete": {"id": "101", "displayName": "Arch Manning"},
                                    "stats": ["20/30", "275", "9.2", "3", "1"],
                                }
                            ],
                        },
                        {
                            "name": "rushing",
                            "keys": ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns"],
                            "athletes": [
                                {
                                    "athlete": {"id": "101", "displayName": "Arch Manning"},
                                    "stats": ["6", "34", "5.7", "1"],
                                }
                            ],
                        },
                        {
                            "name": "receiving",
                            "keys": ["receptions", "receivingYards", "yardsPerReception", "receivingTouchdowns"],
                            "athletes": [
                                {
                                    "athlete": {"id": "202", "displayName": "Ryan Wingo"},
                                    "stats": ["6", "90", "15.0", "1"],
                                }
                            ],
                        },
                        {
                            "name": "fumbles",
                            "keys": ["fumbles", "fumblesLost", "fumblesRecovered"],
                            "athletes": [
                                {
                                    "athlete": {"id": "202", "displayName": "Ryan Wingo"},
                                    "stats": ["1", "1", "0"],
                                }
                            ],
                        },
                        {
                            "name": "kicking",
                            "keys": [
                                "fieldGoalsMade/fieldGoalAttempts",
                                "fieldGoalPct",
                                "longFieldGoalMade",
                                "extraPointsMade/extraPointAttempts",
                            ],
                            "athletes": [
                                {
                                    "athlete": {"id": "303", "displayName": "Bert Auburn"},
                                    "stats": ["2/2", "100.0", "45", "3/3"],
                                }
                            ],
                        },
                    ],
                }
            ]
        },
        "drives": {
            "previous": [
                {
                    "plays": [
                        {"scoringPlay": True, "text": "Bert Auburn 35 Yd Field Goal"},
                        {"scoringPlay": True, "text": "Bert Auburn 45 Yd Field Goal"},
                    ]
                }
            ]
        },
    }


def test_extract_player_box_score_stats_from_espn_summary():
    rows = extract_player_box_score_stats(espn_summary_payload())
    by_name = {row["PlayerName"]: row for row in rows}

    assert by_name["Arch Manning"]["ESPNPlayerID"] == "101"
    assert by_name["Arch Manning"]["pass_yards"] == 275.0
    assert by_name["Arch Manning"]["pass_tds"] == 3.0
    assert by_name["Arch Manning"]["interceptions"] == 1.0
    assert by_name["Arch Manning"]["rush_yards"] == 34.0
    assert by_name["Arch Manning"]["rush_tds"] == 1.0

    assert by_name["Ryan Wingo"]["receptions"] == 6.0
    assert by_name["Ryan Wingo"]["rec_yards"] == 90.0
    assert by_name["Ryan Wingo"]["rec_tds"] == 1.0
    assert by_name["Ryan Wingo"]["fumbles_lost"] == 1.0

    assert by_name["Bert Auburn"]["xp_made"] == 3.0
    assert by_name["Bert Auburn"]["fg_made_0_39"] == 1
    assert by_name["Bert Auburn"]["fg_made_40_49"] == 1


def test_espn_box_score_stats_score_with_league_rules():
    rows = extract_player_box_score_stats(espn_summary_payload())
    receiver = next(row for row in rows if row["PlayerName"] == "Ryan Wingo")

    points, breakdown = calculate_player_fantasy_points(normalize_player_stats(receiver), {"ppr": 0.5})

    assert points == 16.0
    assert breakdown["receptions"]["multiplier"] == 0.5


class FakeESPNClient:
    def get_weekly_boxscore_summaries(self, season, week):
        return [espn_summary_payload()]


def test_upsert_espn_weekly_player_stats_matches_players_by_id_and_name_school(client, db_session):
    by_external_id = Player(name="Arch Manning", position="QB", school="Texas", external_id="espn:101")
    by_name_school = Player(name="Ryan Wingo", position="WR", school="Texas", external_id="sportsdata-202")
    db_session.add_all([by_external_id, by_name_school])
    db_session.commit()

    result = upsert_espn_weekly_player_stats(db_session, season=2026, week=1, client=FakeESPNClient())

    assert result["events"] == 1
    assert result["rows_seen"] == 3
    assert result["upserted"] == 2
    assert result["skipped"] == 1
    arch_stat = db_session.query(PlayerStat).filter_by(player_id=by_external_id.id, season=2026, week=1).one()
    wingo_stat = db_session.query(PlayerStat).filter_by(player_id=by_name_school.id, season=2026, week=1).one()
    assert arch_stat.source == "espn"
    assert arch_stat.stats["pass_yards"] == 275.0
    assert wingo_stat.source == "espn"
    assert wingo_stat.stats["rec_tds"] == 1.0
