"""Source-gated, deterministic player-enrichment imports.

This module deliberately consumes *staged exports*, never a live provider.
Production operators must review a dry-run and verify a logical database backup
before using an apply command.  It never changes canonical player identity,
preseason projections, or current value ratings.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.models.college_team import CollegeTeam
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.provider_identity import ProviderIdentityConflict, upsert_player_provider_mapping


class MatchOutcome(StrEnum):
    EXACT = "EXACT"
    VERIFIED_ALIAS = "VERIFIED_ALIAS"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"


IDENTITY_FIELDS = {
    "provider", "provider_player_id", "provider_team_id", "provider_team_name", "player_name", "school", "position",
}
BIO_FIELDS = {
    "height", "weight", "birthplace", "jersey", "player_class", "profile_status", "headshot_url", "headshot_approved",
}
HISTORICAL_NUMERIC_FIELDS = {
    "games_played", "games_started", "passing_completions", "passing_attempts", "passing_yards", "passing_touchdowns",
    "interceptions", "sacks_taken", "rushing_attempts", "rushing_yards", "rushing_touchdowns", "long_rush", "receptions",
    "receiving_targets", "receiving_yards", "receiving_touchdowns", "long_reception", "kick_return_attempts",
    "kick_return_yards", "kick_return_touchdowns", "punt_return_attempts", "punt_return_yards", "punt_return_touchdowns",
    "field_goals_made", "field_goals_attempted", "field_goals_0_19", "field_goals_20_29", "field_goals_30_39",
    "field_goals_40_49", "field_goals_50_plus", "extra_points_made", "extra_points_attempted", "kick_points",
    "fumbles", "fumbles_lost",
}
WEEKLY_NUMERIC_FIELDS = {
    "pass_attempts", "rush_attempts", "targets", "receptions", "expected_plays", "expected_rush_per_play",
    "expected_td_per_play", "pass_yards", "rush_yards", "rec_yards", "pass_tds", "rush_tds", "rec_tds",
    "interceptions", "field_goals_made_0_to_39", "field_goals_made_40_to_49", "field_goals_made_0_to_49",
    "field_goals_made_50_plus", "extra_points_made", "neutral_baseline", "availability_multiplier", "usage_multiplier",
    "offense_multiplier", "opponent_defense_multiplier", "confidence", "fantasy_points", "floor", "ceiling", "boom_prob", "bust_prob",
}


def normalized(value: object | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).lower().replace("&", "and")
    return "".join(character for character in text if character.isalnum())


def text(value: object | None) -> str | None:
    normalized_value = str(value or "").strip()
    return normalized_value or None


def number(value: object | None) -> float | None:
    raw = text(value)
    if raw is None:
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"expected numeric value, received {raw!r}") from exc


def boolean(value: object | None) -> bool:
    return (text(value) or "").lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class EnrichmentSourceRow:
    row_number: int
    values: dict[str, str]

    def value(self, key: str) -> str | None:
        return text(self.values.get(key))


@dataclass(frozen=True)
class MatchResult:
    outcome: MatchOutcome
    player_id: int | None = None
    detail: str | None = None


@dataclass
class EnrichmentReport:
    stage: str
    source_rows: int = 0
    exact: int = 0
    verified_alias: int = 0
    ambiguous: int = 0
    not_found: int = 0
    conflicts: int = 0
    ready: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    manual_review: list[dict[str, Any]] = field(default_factory=list)

    def add(self, result: MatchResult, row: EnrichmentSourceRow) -> None:
        setattr(self, result.outcome.value.lower(), getattr(self, result.outcome.value.lower()) + 1)
        if result.outcome in {MatchOutcome.EXACT, MatchOutcome.VERIFIED_ALIAS}:
            self.ready += 1
        else:
            self.manual_review.append({"row_number": row.row_number, "outcome": result.outcome, "detail": result.detail})

    @property
    def has_unresolved_identity_conflicts(self) -> bool:
        return any((self.ambiguous, self.not_found, self.conflicts))

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage, "source_rows": self.source_rows, "exact": self.exact,
            "verified_alias": self.verified_alias, "ambiguous": self.ambiguous, "not_found": self.not_found,
            "conflicts": self.conflicts, "ready": self.ready, "inserted": self.inserted,
            "updated": self.updated, "unchanged": self.unchanged, "manual_review": self.manual_review,
        }


def read_csv_rows(path: Path, *, required: Iterable[str]) -> list[EnrichmentSourceRow]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        headers = set(reader.fieldnames or [])
        missing = sorted(set(required) - headers)
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {', '.join(missing)}")
        return [EnrichmentSourceRow(index, {key: value or "" for key, value in row.items()}) for index, row in enumerate(reader, 2)]


def read_verified_aliases(path: Path | None) -> dict[tuple[str, str], int]:
    if path is None:
        return {}
    aliases = read_csv_rows(path, required={"provider", "provider_player_id", "player_id"})
    result: dict[tuple[str, str], int] = {}
    for alias in aliases:
        provider, provider_id, player_id = alias.value("provider"), alias.value("provider_player_id"), alias.value("player_id")
        if not provider or not provider_id or not player_id or not player_id.isdigit():
            raise ValueError(f"invalid verified alias at row {alias.row_number}")
        key = (provider.lower(), provider_id)
        if key in result:
            raise ValueError(f"duplicate verified alias at row {alias.row_number}")
        result[key] = int(player_id)
    return result


def _compatible(player: Player, row: EnrichmentSourceRow) -> bool:
    return (
        normalized(player.school) == normalized(row.value("school"))
        and (player.position or "").upper() == (row.value("position") or "").upper()
    )


def resolve_identity(
    db: Session,
    row: EnrichmentSourceRow,
    *,
    approved_aliases: dict[tuple[str, str], int] | None = None,
) -> MatchResult:
    """Resolve only a full canonical identity or an explicit reviewed alias."""
    provider, provider_id = row.value("provider"), row.value("provider_player_id")
    if not provider or not provider_id:
        return MatchResult(MatchOutcome.NOT_FOUND, detail="provider and provider_player_id are required")
    mappings = db.scalars(
        select(PlayerProviderId).where(
            PlayerProviderId.provider == provider.lower(), PlayerProviderId.provider_player_id == provider_id
        )
    ).all()
    if len(mappings) > 1:
        return MatchResult(MatchOutcome.CONFLICT, detail="provider ID maps to multiple canonical players")
    if mappings:
        player = db.get(Player, mappings[0].player_id)
        if player and _compatible(player, row):
            return MatchResult(MatchOutcome.EXACT, player.id, "existing verified provider mapping")
        return MatchResult(MatchOutcome.CONFLICT, detail="provider ID identity conflicts with canonical player")
    alias_id = (approved_aliases or {}).get((provider.lower(), provider_id))
    if alias_id is not None:
        player = db.get(Player, alias_id)
        if player is None or not _compatible(player, row):
            return MatchResult(MatchOutcome.CONFLICT, detail="verified alias does not match canonical school and position")
        return MatchResult(MatchOutcome.VERIFIED_ALIAS, player.id, "reviewed provider ID alias")
    candidates = db.scalars(select(Player).where(Player.name == (row.value("player_name") or ""))).all()
    exact = [candidate for candidate in candidates if _compatible(candidate, row)]
    if len(exact) == 1:
        return MatchResult(MatchOutcome.EXACT, exact[0].id, "name, school, and position")
    if len(exact) > 1:
        return MatchResult(MatchOutcome.AMBIGUOUS, detail="multiple canonical players share the full identity")
    if candidates:
        return MatchResult(MatchOutcome.CONFLICT, detail="name found but canonical school or position differs")
    return MatchResult(MatchOutcome.NOT_FOUND, detail="no canonical player has this name, school, and position")


def _existing_player_mappings(db: Session, player_id: int, provider: str) -> PlayerProviderId | None:
    return db.scalar(select(PlayerProviderId).where(PlayerProviderId.player_id == player_id, PlayerProviderId.provider == provider.lower()))


def import_identities_and_bios(
    db: Session, rows: list[EnrichmentSourceRow], *, approved_aliases: dict[tuple[str, str], int], apply: bool
) -> EnrichmentReport:
    report = EnrichmentReport(stage="identities")
    for row in rows:
        report.source_rows += 1
        result = resolve_identity(db, row, approved_aliases=approved_aliases)
        report.add(result, row)
        if result.player_id is None:
            continue
        player = db.get(Player, result.player_id)
        assert player is not None
        provider, provider_id = row.value("provider"), row.value("provider_player_id")
        assert provider and provider_id
        existing = _existing_player_mappings(db, player.id, provider)
        bio_values = {
            "espn_height": row.value("height"), "espn_weight": row.value("weight"), "espn_birthplace": row.value("birthplace"),
            "espn_jersey": row.value("jersey"), "player_class": row.value("player_class"), "espn_status": row.value("profile_status"),
            "bio_source": provider.lower(), "espn_source_url": row.value("source_url"),
        }
        if boolean(row.value("headshot_approved")):
            bio_values["espn_headshot_url"] = row.value("headshot_url")
        changed = existing is None or any(getattr(player, key) != value for key, value in bio_values.items() if value is not None)
        if not changed:
            report.unchanged += 1
            continue
        if apply:
            try:
                upsert_player_provider_mapping(
                    db, player_id=player.id, provider=provider, provider_player_id=provider_id,
                    provider_team_id=row.value("provider_team_id"), match_confidence=1.0,
                    verification_status="verified", reason="approved staged enrichment import",
                )
            except ProviderIdentityConflict as exc:
                raise ValueError(f"identity conflict at source row {row.row_number}: {exc}") from exc
            for key, value in bio_values.items():
                if value is not None:
                    setattr(player, key, value)
            player.espn_profile_synced_at = datetime.now(timezone.utc)
        report.updated += int(existing is not None)
        report.inserted += int(existing is None)
    return report


def import_historical_totals(
    db: Session, rows: list[EnrichmentSourceRow], *, approved_aliases: dict[tuple[str, str], int], apply: bool, source_sha256: str
) -> EnrichmentReport:
    report = EnrichmentReport(stage="historical")
    for row in rows:
        report.source_rows += 1
        result = resolve_identity(db, row, approved_aliases=approved_aliases)
        report.add(result, row)
        season = row.value("season")
        if result.player_id is None or not season or not season.isdigit():
            if result.player_id is not None:
                report.conflicts += 1
                report.manual_review.append({"row_number": row.row_number, "outcome": MatchOutcome.CONFLICT, "detail": "valid season is required"})
            continue
        player = db.get(Player, result.player_id)
        assert player is not None
        provider, provider_id = row.value("provider"), row.value("provider_player_id")
        assert provider and provider_id
        season_number = int(season)
        team_name = row.value("historical_team") or row.value("school")
        existing = db.scalar(select(PlayerHistoricalSeasonStat).where(
            PlayerHistoricalSeasonStat.player_id == player.id, PlayerHistoricalSeasonStat.provider == provider.lower(),
            PlayerHistoricalSeasonStat.season == season_number, PlayerHistoricalSeasonStat.season_type == (row.value("season_type") or "regular"),
            PlayerHistoricalSeasonStat.team_name == team_name,
        ))
        values = {field: number(row.value(field)) for field in HISTORICAL_NUMERIC_FIELDS if row.value(field) is not None}
        if existing and all(getattr(existing, key) == value for key, value in values.items()) and existing.source_response_hash == source_sha256:
            report.unchanged += 1
            continue
        if apply:
            target = existing or PlayerHistoricalSeasonStat(
                player_id=player.id, provider=provider.lower(), provider_player_id=provider_id, season=season_number,
                season_type=row.value("season_type") or "regular", team_name=team_name, parser_version="staged-enrichment-v1",
                imported_at=datetime.now(timezone.utc),
            )
            for key, value in values.items():
                setattr(target, key, value)
            target.provider_team_id = row.value("provider_team_id")
            target.position = row.value("position")
            target.canonical_position = player.position
            target.source_response_hash = source_sha256
            target.source_url = row.value("source_url")
            target.source_type = "approved_staged_export"
            target.import_version = f"staged-enrichment:{source_sha256[:12]}"
            target.parser_version = "staged-enrichment-v1"
            target.imported_at = datetime.now(timezone.utc)
            # Do not invent fantasy totals; historical scoring is calculated only when a complete approved scoring contract exists.
            target.fantasy_points = None
            target.fantasy_points_per_game = None
            target.scoring_rules_version = None
            if existing is None:
                db.add(target)
        report.updated += int(existing is not None)
        report.inserted += int(existing is None)
    return report


def import_completed_weekly_stats(
    db: Session, rows: list[EnrichmentSourceRow], *, approved_aliases: dict[tuple[str, str], int], apply: bool
) -> EnrichmentReport:
    report = EnrichmentReport(stage="completed-stats")
    for row in rows:
        report.source_rows += 1
        result = resolve_identity(db, row, approved_aliases=approved_aliases)
        report.add(result, row)
        season, week, stats_json = row.value("season"), row.value("week"), row.value("stats_json")
        if result.player_id is None or not season or not season.isdigit() or not week or not week.isdigit() or not stats_json:
            if result.player_id is not None:
                report.conflicts += 1
                report.manual_review.append({"row_number": row.row_number, "outcome": MatchOutcome.CONFLICT, "detail": "season, week, and stats_json are required"})
            continue
        try:
            stats = json.loads(stats_json)
        except json.JSONDecodeError:
            report.conflicts += 1
            report.manual_review.append({"row_number": row.row_number, "outcome": MatchOutcome.CONFLICT, "detail": "stats_json is invalid"})
            continue
        if not isinstance(stats, dict):
            report.conflicts += 1
            report.manual_review.append({"row_number": row.row_number, "outcome": MatchOutcome.CONFLICT, "detail": "stats_json must be an object"})
            continue
        existing = db.scalar(select(PlayerStat).where(PlayerStat.player_id == result.player_id, PlayerStat.season == int(season), PlayerStat.week == int(week)))
        if existing and existing.stats == stats and existing.source == (row.value("provider") or "approved_staged_export"):
            report.unchanged += 1
            continue
        if apply:
            if existing is None:
                db.add(PlayerStat(player_id=result.player_id, season=int(season), week=int(week), stats=stats, source=row.value("provider") or "approved_staged_export"))
            else:
                existing.stats = stats
                existing.source = row.value("provider") or "approved_staged_export"
                existing.verified = True
        report.updated += int(existing is not None)
        report.inserted += int(existing is None)
    return report


def import_weekly_projections(
    db: Session, rows: list[EnrichmentSourceRow], *, approved_aliases: dict[tuple[str, str], int], apply: bool
) -> EnrichmentReport:
    """Import an approved week-specific projection file; never derive a week from a season total."""
    report = EnrichmentReport(stage="weekly-projections")
    for row in rows:
        report.source_rows += 1
        result = resolve_identity(db, row, approved_aliases=approved_aliases)
        report.add(result, row)
        season, week, version = row.value("season"), row.value("week"), row.value("projection_version")
        supplied_values = {field: number(row.value(field)) for field in WEEKLY_NUMERIC_FIELDS}
        if (
            result.player_id is None or not season or not season.isdigit() or not week or not week.isdigit()
            or not version or any(value is None for value in supplied_values.values())
        ):
            if result.player_id is not None:
                report.conflicts += 1
                report.manual_review.append({
                    "row_number": row.row_number, "outcome": MatchOutcome.CONFLICT,
                    "detail": "weekly projections require season, week, version, and every published numeric field",
                })
            continue
        if len(version) > 20:
            report.conflicts += 1
            report.manual_review.append({"row_number": row.row_number, "outcome": MatchOutcome.CONFLICT, "detail": "projection_version exceeds 20 characters"})
            continue
        team = db.scalar(select(CollegeTeam).where(CollegeTeam.name == (row.value("school") or "")))
        if team is None:
            report.conflicts += 1
            report.manual_review.append({"row_number": row.row_number, "outcome": MatchOutcome.CONFLICT, "detail": "canonical team is not registered"})
            continue
        opponent_name = row.value("opponent_team")
        opponent = db.scalar(select(CollegeTeam).where(CollegeTeam.name == opponent_name)) if opponent_name else None
        if opponent_name and opponent is None:
            report.conflicts += 1
            report.manual_review.append({"row_number": row.row_number, "outcome": MatchOutcome.CONFLICT, "detail": "opponent team is not registered"})
            continue
        existing = db.scalar(select(WeeklyProjection).where(
            WeeklyProjection.player_id == result.player_id, WeeklyProjection.season == int(season),
            WeeklyProjection.week == int(week), WeeklyProjection.projection_version == version,
        ))
        values = {
            **supplied_values,
            "is_published": boolean(row.value("is_published")),
            "projection_status": row.value("projection_status") or "ACTIVE",
            "model_version": row.value("model_version") or "approved-staged-v1",
            "team_id": team.id,
            "opponent_team_id": opponent.id if opponent else None,
            "baseline_games_played": int(number(row.value("baseline_games_played")) or 0),
            "baseline_source": row.value("baseline_source") or "approved_staged_export",
            "fallback_reason": row.value("fallback_reason"),
        }
        if existing and all(getattr(existing, key) == value for key, value in values.items()):
            report.unchanged += 1
            continue
        if apply:
            target = existing or WeeklyProjection(
                player_id=result.player_id, season=int(season), week=int(week), projection_version=version
            )
            for key, value in values.items():
                setattr(target, key, value)
            if existing is None:
                db.add(target)
        report.updated += int(existing is not None)
        report.inserted += int(existing is None)
    return report


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_logical_backup(manifest_path: Path) -> dict[str, Any]:
    """Require a readable, checksum-verified logical backup before any apply run."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backup_path = Path(manifest["path"]).expanduser()
    expected_hash = manifest["sha256"]
    if not backup_path.is_file() or source_sha256(backup_path) != expected_hash:
        raise ValueError("logical backup is missing or its SHA-256 checksum does not match the manifest")
    if backup_path.stat().st_size == 0:
        raise ValueError("logical backup is empty")
    return {"path": str(backup_path), "sha256": expected_hash, "size": backup_path.stat().st_size}
