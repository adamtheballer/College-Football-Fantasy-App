"""One shared calculation for persisted regular-season records and read-side proof."""
from collections.abc import Iterable

from collegefootballfantasy_api.app.models.matchup import Matchup

FINAL_MATCHUP_STATUSES = {"final", "stat_corrected"}


def finalized_matchup_records(matchups: Iterable[Matchup], team_ids: Iterable[int]) -> dict[int, dict[str, int | float]]:
    records = {
        team_id: {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0}
        for team_id in team_ids
    }
    for matchup in matchups:
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            continue
        home = records.setdefault(matchup.home_team_id, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0})
        away = records.setdefault(matchup.away_team_id, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0})
        home_score = float(matchup.home_score or 0.0)
        away_score = float(matchup.away_score or 0.0)
        home["points_for"] += home_score
        home["points_against"] += away_score
        away["points_for"] += away_score
        away["points_against"] += home_score
        if home_score > away_score:
            home["wins"] += 1
            away["losses"] += 1
        elif away_score > home_score:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["ties"] += 1
            away["ties"] += 1
    return records


def record_application_fingerprint(matchup: Matchup, home_record: dict | None, away_record: dict | None) -> str | None:
    """Receipt for an exact finalized result and both applied cumulative records."""
    import hashlib
    import json
    if (matchup.status or '').lower() not in FINAL_MATCHUP_STATUSES or home_record is None or away_record is None:
        return None
    def snapshot(record):
        return {key: int(record[key]) for key in ('wins', 'losses', 'ties')} | {
            key: round(float(record[key]), 2) for key in ('points_for', 'points_against')
        }
    try:
        source = {'version':1,'league_id':matchup.league_id,'season':matchup.season,'week':matchup.week,'matchup_id':matchup.id,
                  'home_team_id':matchup.home_team_id,'away_team_id':matchup.away_team_id,
                  'status':matchup.status.lower(),'home_score':float(matchup.home_score or 0),'away_score':float(matchup.away_score or 0),
                  'home_record':snapshot(home_record),'away_record':snapshot(away_record)}
        return hashlib.sha256(json.dumps(source,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
    except (ValueError, TypeError, KeyError):
        return None
