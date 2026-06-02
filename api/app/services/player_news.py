from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_news_snapshot import PlayerNewsSnapshot
from collegefootballfantasy_api.app.schemas.player_stat import PlayerSeasonTotals

ALONZA_BARNETT_SOURCE_URLS = [
    "https://ucfknights.com/news/2026/1/4/2026-football-transfer-portal-central",
    "https://jmusports.com/documents/download/2026/1/20/JMUFinalStats2025.pdf",
]


@dataclass
class LatestNewsResult:
    text: str
    source_type: str
    sources: list[str]
    verified_at: datetime | None = None


def _ensure_transfer_seed(db: Session) -> None:
    player = (
        db.query(Player)
        .filter(Player.name.ilike("Alonza Barnett III"))
        .first()
    )
    if not player:
        return

    existing = (
        db.query(PlayerNewsSnapshot)
        .filter(
            PlayerNewsSnapshot.player_id == player.id,
            PlayerNewsSnapshot.season == 2026,
        )
        .first()
    )
    if existing:
        return

    summary = (
        "Transferred from James Madison to UCF after a strong 2025 season as a dual-threat quarterback. "
        "Barnett's mobility and red-zone usage should immediately raise his weekly floor, and UCF projects "
        "to build around his run-pass conflict ability in 2026/27."
    )
    db.add(
        PlayerNewsSnapshot(
            player_id=player.id,
            season=2026,
            summary=summary,
            source_type="verified_override",
            is_transfer=True,
            from_school="James Madison",
            to_school="UCF",
            expected_role="Projected starting QB with designed-run usage.",
            source_urls=ALONZA_BARNETT_SOURCE_URLS,
            verified_at=datetime.now(timezone.utc),
        )
    )
    db.flush()


def _extract_sheet_news(player: Player) -> str | None:
    payload = player.sheet_projection_stats or {}
    if not isinstance(payload, dict):
        return None
    for key in ("latest_news", "latestNews", "news", "outlook", "analysis"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _meaningful_totals(totals: PlayerSeasonTotals) -> bool:
    if totals.games <= 0:
        return False
    workload = (
        totals.passing_attempts
        + totals.rushing_attempts
        + totals.receptions
        + totals.field_goals_made
        + totals.extra_points_made
    )
    production = (
        totals.passing_yards
        + totals.rushing_yards
        + totals.receiving_yards
        + totals.passing_tds
        + totals.rushing_tds
        + totals.receiving_tds
    )
    return workload > 0 or production > 0


def _safe_stats_brief(player: Player, season: int, totals: PlayerSeasonTotals) -> str:
    games = max(1, int(totals.games))
    position = (player.position or "").upper()
    if position == "QB":
        return (
            f"{player.name} enters {season + 1} with {totals.passing_yards:,.0f} passing yards and "
            f"{totals.passing_tds:,.0f} pass TDs from {season}, plus {totals.rushing_yards:,.0f} rushing yards. "
            "Projection remains tied to volume and designed-run usage."
        )
    if position == "RB":
        return (
            f"{player.name} posted {totals.rushing_yards:,.0f} rushing yards and {totals.rushing_tds:,.0f} rushing TDs in {season}, "
            f"adding {totals.receptions:,.0f} receptions. Opportunity profile remains strong entering {season + 1}."
        )
    if position in {"WR", "TE"}:
        return (
            f"{player.name} produced {totals.receptions:,.0f} catches for {totals.receiving_yards:,.0f} yards and "
            f"{totals.receiving_tds:,.0f} receiving TDs in {season}. Target concentration and QB fit will drive ceiling in {season + 1}."
        )
    if position == "K":
        return (
            f"{player.name} converted {totals.field_goals_made:,.0f} field goals and {totals.extra_points_made:,.0f} extra points in {season}. "
            "Fantasy value tracks team scoring volume."
        )
    return (
        f"{player.name} has limited published fantasy-relevant counting stats from {season}. "
        f"Role and depth-chart stability at {player.school} will determine upside in {season + 1}."
    )


def _fallback_context(player: Player, season: int) -> str:
    return (
        f"No verified in-season stat line is available yet for {player.name}. "
        f"Projection context for {season + 1} currently relies on depth-chart role and team environment at {player.school}."
    )


def build_player_latest_news(
    db: Session,
    *,
    player: Player,
    season: int,
    totals: PlayerSeasonTotals,
) -> LatestNewsResult:
    _ensure_transfer_seed(db)

    override = (
        db.query(PlayerNewsSnapshot)
        .filter(
            PlayerNewsSnapshot.player_id == player.id,
            PlayerNewsSnapshot.season == season + 1,
        )
        .first()
    )
    if override and override.summary.strip():
        return LatestNewsResult(
            text=override.summary.strip(),
            source_type="verified_override",
            sources=[str(url) for url in (override.source_urls or []) if str(url).strip()],
            verified_at=override.verified_at,
        )

    sheet_news = _extract_sheet_news(player)
    if sheet_news:
        return LatestNewsResult(
            text=sheet_news,
            source_type="sheet",
            sources=[],
            verified_at=None,
        )

    if _meaningful_totals(totals):
        return LatestNewsResult(
            text=_safe_stats_brief(player, season, totals),
            source_type="generated_stats",
            sources=[],
            verified_at=None,
        )

    return LatestNewsResult(
        text=_fallback_context(player, season),
        source_type="fallback_context",
        sources=[],
        verified_at=None,
    )
