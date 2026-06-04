from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.app.models.player import Player
from api.app.services.news_relevance import POWER_FOUR_TEAMS


@dataclass
class NewsMatch:
    player_id: int | None = None
    player_name_raw: str | None = None
    team_name_raw: str | None = None
    canonical_team: str | None = None
    position: str | None = None
    confidence_score: float = 0.0


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9]){re.escape(phrase.lower())}(?![A-Za-z0-9])"
    return re.search(pattern, text) is not None


def match_news_entities(db: Session, *, title: str, summary: str | None = None) -> NewsMatch:
    text = f"{title or ''} {summary or ''}".lower()
    matched_team = next((team for team in sorted(POWER_FOUR_TEAMS, key=len, reverse=True) if _contains_phrase(text, team)), None)
    players = db.query(Player).all()
    matched_players = [player for player in players if _contains_phrase(text, player.name)]
    if not matched_players:
        return NewsMatch(
            team_name_raw=matched_team,
            canonical_team=matched_team,
            confidence_score=0.35 if matched_team else 0.0,
        )
    if len(matched_players) == 1:
        player = matched_players[0]
        school_matches = bool(matched_team and player.school and matched_team.lower() == player.school.lower())
        return NewsMatch(
            player_id=player.id,
            player_name_raw=player.name,
            team_name_raw=matched_team or player.school,
            canonical_team=matched_team or player.school,
            position=player.position,
            confidence_score=0.95 if school_matches else 0.75,
        )
    if matched_team:
        school_matches = [player for player in matched_players if player.school and player.school.lower() == matched_team.lower()]
        if len(school_matches) == 1:
            player = school_matches[0]
            return NewsMatch(
                player_id=player.id,
                player_name_raw=player.name,
                team_name_raw=matched_team,
                canonical_team=matched_team,
                position=player.position,
                confidence_score=0.95,
            )
    return NewsMatch(
        player_name_raw=", ".join(player.name for player in matched_players[:3]),
        team_name_raw=matched_team,
        canonical_team=matched_team,
        confidence_score=0.4,
    )
