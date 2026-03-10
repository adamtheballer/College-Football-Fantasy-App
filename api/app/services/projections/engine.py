from __future__ import annotations

from math import erf, sqrt
from typing import Any

from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points, get_scoring_rules
from collegefootballfantasy_api.app.services.projections.efficiency import compute_efficiency


DEFAULT_QB = {"ypa": 7.5, "pass_td_rate": 0.05, "int_rate": 0.02, "rush_ypc": 4.5, "comp_pct": 0.62}
DEFAULT_RB = {"ypc": 4.5, "ypt": 6.5, "catch_rate": 0.72}
DEFAULT_WR = {"ypt": 8.5, "catch_rate": 0.62}
DEFAULT_TE = {"ypt": 7.5, "catch_rate": 0.68}


def _normal_cdf(x: float, mean: float, sd: float) -> float:
    if sd <= 0:
        return 0.0
    z = (x - mean) / (sd * sqrt(2))
    return 0.5 * (1 + erf(z))


def _health_multiplier(status: str | None) -> float:
    if not status:
        return 1.0
    status = status.upper()
    if status == "OUT":
        return 0.0
    if status == "DOUBTFUL":
        return 0.2
    if status == "QUESTIONABLE":
        return 0.7
    if status == "PROBABLE":
        return 0.9
    return 1.0


def _qb_rating(comp_pct: float, ypa: float, td_rate: float, int_rate: float) -> float:
    rating = (8.4 * ypa) + (330 * td_rate) + (100 * comp_pct) - (200 * int_rate)
    return round(rating, 2)


def build_weekly_projections(
    players: list[Player],
    team_env_by_team: dict[str, TeamEnvironment],
    usage_by_player: dict[int, UsageShare],
    defense_by_team: dict[str, DefenseRating],
    player_stats: dict[int, dict[str, Any]],
    injuries_by_player: dict[int, Injury],
    opponent_by_team: dict[str, str] | None,
    season: int,
    week: int,
) -> list[WeeklyProjection]:
    opponent_by_team = opponent_by_team or {}
    rules = get_scoring_rules()
    projections: list[WeeklyProjection] = []

    for player in players:
        team_env = team_env_by_team.get(player.school)
        if not team_env:
            continue

        usage = usage_by_player.get(player.id)
        if not usage:
            continue

        injury = injuries_by_player.get(player.id)
        health = _health_multiplier(injury.status if injury else None)

        opp_team = opponent_by_team.get(player.school)
        defense = defense_by_team.get(opp_team) if opp_team else None

        team_pass_attempts = team_env.expected_plays * team_env.pass_rate
        team_rush_attempts = team_env.expected_plays * team_env.rush_rate

        player_targets = team_pass_attempts * usage.target_share * health
        player_rush_attempts = team_rush_attempts * usage.rush_share * health

        stats = player_stats.get(player.id, {})
        eff = compute_efficiency(stats, player.position)

        if player.position.upper() == "QB":
            baseline = DEFAULT_QB | eff
            pass_td_rate = baseline["pass_td_rate"]
            int_rate = baseline["int_rate"]
            ypa = baseline["ypa"]
            comp_pct = baseline["comp_pct"]

            if defense:
                ypa *= defense.pass_yards_multiplier
                pass_td_rate *= defense.pass_td_multiplier
                int_rate *= defense.pass_turnover_multiplier

            pass_attempts = team_pass_attempts * health
            pass_yards = pass_attempts * ypa
            pass_tds = pass_attempts * pass_td_rate
            interceptions = pass_attempts * int_rate

            rush_ypc = baseline["rush_ypc"]
            if defense:
                rush_ypc *= defense.rush_yards_multiplier
            rush_yards = player_rush_attempts * rush_ypc
            rush_tds = player_rush_attempts * 0.02

            qb_rating = _qb_rating(comp_pct, ypa, pass_td_rate, int_rate)

            expected_plays = pass_attempts + player_rush_attempts
            expected_rush_per_play = player_rush_attempts / max(team_env.expected_plays, 1.0)
            expected_td_per_play = (pass_tds + rush_tds) / max(expected_plays, 1.0)

            stats_row = {
                "PassingYards": pass_yards,
                "PassingTouchdowns": pass_tds,
                "PassingInterceptions": interceptions,
                "RushingYards": rush_yards,
                "RushingTouchdowns": rush_tds,
            }
            fpts = calculate_fantasy_points(stats_row, rules, position="QB")

            sd = max(2.0, fpts * 0.35)
            floor = max(0.0, fpts - sd)
            ceiling = fpts + sd
            boom_prob = 1 - _normal_cdf(fpts * 1.5, fpts, sd)
            bust_prob = _normal_cdf(fpts * 0.5, fpts, sd)

            projections.append(
                WeeklyProjection(
                    player_id=player.id,
                    season=season,
                    week=week,
                    pass_attempts=pass_attempts,
                    rush_attempts=player_rush_attempts,
                    targets=0.0,
                    receptions=0.0,
                    expected_plays=expected_plays,
                    expected_rush_per_play=expected_rush_per_play,
                    expected_td_per_play=expected_td_per_play,
                    pass_yards=pass_yards,
                    rush_yards=rush_yards,
                    rec_yards=0.0,
                    pass_tds=pass_tds,
                    rush_tds=rush_tds,
                    rec_tds=0.0,
                    interceptions=interceptions,
                    fantasy_points=fpts,
                    floor=floor,
                    ceiling=ceiling,
                    boom_prob=boom_prob,
                    bust_prob=bust_prob,
                    qb_rating=qb_rating,
                )
            )
            continue

        if player.position.upper() in {"RB", "WR", "TE"}:
            if player.position.upper() == "RB":
                baseline = DEFAULT_RB | eff
                ypc = baseline["ypc"]
                ypt = baseline["ypt"]
                catch_rate = baseline["catch_rate"]
            elif player.position.upper() == "WR":
                baseline = DEFAULT_WR | eff
                ypt = baseline["ypt"]
                catch_rate = baseline["catch_rate"]
                ypc = 0.0
            else:
                baseline = DEFAULT_TE | eff
                ypt = baseline["ypt"]
                catch_rate = baseline["catch_rate"]
                ypc = 0.0

            if defense:
                ypt *= defense.pass_yards_multiplier
                catch_rate *= defense.pass_catch_multiplier
                ypc *= defense.rush_yards_multiplier

            receptions = player_targets * catch_rate
            rec_yards = player_targets * ypt
            rush_yards = player_rush_attempts * ypc

            rec_td_rate = 0.05 if player.position.upper() in {"WR", "TE"} else 0.03
            rush_td_rate = 0.03 if player.position.upper() == "RB" else 0.01
            if defense:
                rec_td_rate *= defense.pass_td_multiplier
                rush_td_rate *= defense.rush_td_multiplier

            rec_tds = player_targets * rec_td_rate
            rush_tds = player_rush_attempts * rush_td_rate

            expected_plays = player_rush_attempts + player_targets
            expected_rush_per_play = player_rush_attempts / max(team_env.expected_plays, 1.0)
            expected_td_per_play = (rush_tds + rec_tds) / max(expected_plays, 1.0)

            stats_row = {
                "RushingYards": rush_yards,
                "RushingTouchdowns": rush_tds,
                "Receptions": receptions,
                "ReceivingYards": rec_yards,
                "ReceivingTouchdowns": rec_tds,
            }
            fpts = calculate_fantasy_points(stats_row, rules, position=player.position.upper())

            sd = max(1.5, fpts * 0.30)
            floor = max(0.0, fpts - sd)
            ceiling = fpts + sd
            boom_prob = 1 - _normal_cdf(fpts * 1.5, fpts, sd)
            bust_prob = _normal_cdf(fpts * 0.5, fpts, sd)

            projections.append(
                WeeklyProjection(
                    player_id=player.id,
                    season=season,
                    week=week,
                    pass_attempts=0.0,
                    rush_attempts=player_rush_attempts,
                    targets=player_targets,
                    receptions=receptions,
                    expected_plays=expected_plays,
                    expected_rush_per_play=expected_rush_per_play,
                    expected_td_per_play=expected_td_per_play,
                    pass_yards=0.0,
                    rush_yards=rush_yards,
                    rec_yards=rec_yards,
                    pass_tds=0.0,
                    rush_tds=rush_tds,
                    rec_tds=rec_tds,
                    interceptions=0.0,
                    fantasy_points=fpts,
                    floor=floor,
                    ceiling=ceiling,
                    boom_prob=boom_prob,
                    bust_prob=bust_prob,
                    qb_rating=None,
                )
            )

    return projections
