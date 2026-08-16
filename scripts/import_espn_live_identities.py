#!/usr/bin/env python3
"""Dry-run-first ESPN identity and schedule reference importer.

This command is intentionally offline from the live scorer: it makes a small,
cached set of public ESPN reference requests, plans exact mappings, and only
writes records that are unambiguous after team, name, position, and profile
checks agree. It never uses a name fallback at scoring time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school
from collegefootballfantasy_api.app.services.provider_identity import ProviderIdentityConflict, upsert_player_provider_mapping


PARSER_VERSION = "espn-identity-import-v1"
POSITION_ALIASES = {
    "QUARTERBACK": "QB",
    "RUNNING BACK": "RB",
    "WIDE RECEIVER": "WR",
    "TIGHT END": "TE",
    "PLACE KICKER": "K",
    "KICKER": "K",
    "PK": "K",
}
def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RateLimitPaused(RuntimeError):
    def __init__(self, resume_at: datetime) -> None:
        self.resume_at = resume_at
        super().__init__(f"ESPN reference import paused until {resume_at.isoformat()}")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def normalize_exact_name(value: str | None) -> str:
    """Normalize only presentation differences; retain generational suffixes."""

    tokens = re.findall(r"[a-z0-9]+", (value or "").lower().replace("&", " and "))
    return " ".join(tokens)


def _school_key(value: str | None) -> str:
    text = str(value or "").strip()
    return canonical_school_name(text) or normalize_school(text)


def _position(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("abbreviation") or value.get("displayName") or value.get("name")
    text = str(value or "").strip().upper()
    return POSITION_ALIASES.get(text, text)


def _review_priority(player: Player) -> str:
    """Rank review order only; never relax the verification contract."""

    if (player.depth_order or 99) <= 1 or (player.sheet_adp or float("inf")) <= 120:
        return "P0"
    if (player.depth_order or 99) <= 2 or (player.sheet_adp or float("inf")) <= 350:
        return "P1"
    return "P2"


def _athlete_name(row: dict[str, Any]) -> str:
    return str(row.get("displayName") or row.get("fullName") or row.get("name") or "").strip()


def flatten_roster(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the minimal authoritative facts used by identity planning."""

    athletes: list[dict[str, Any]] = []
    for group in payload.get("athletes", []) if isinstance(payload, dict) else []:
        if not isinstance(group, dict):
            continue
        for raw in group.get("items", []) if isinstance(group.get("items"), list) else []:
            if not isinstance(raw, dict) or not str(raw.get("id") or "").strip().isdigit():
                continue
            college = raw.get("college") if isinstance(raw.get("college"), dict) else {}
            athletes.append(
                {
                    "espn_player_id": str(raw["id"]).strip(),
                    "espn_display_name": _athlete_name(raw),
                    "espn_team": str(college.get("name") or college.get("shortName") or "").strip(),
                    "espn_team_id": str(college.get("id") or "").strip() or None,
                    "espn_position": _position(raw.get("position")),
                }
            )
    return athletes


def profile_facts(payload: dict[str, Any]) -> dict[str, str | None]:
    athlete = payload.get("athlete") if isinstance(payload, dict) else None
    athlete = athlete if isinstance(athlete, dict) else {}
    team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
    return {
        "espn_player_id": str(athlete.get("id") or "").strip() or None,
        "espn_display_name": _athlete_name(athlete),
        "espn_team": str(team.get("location") or team.get("shortDisplayName") or team.get("name") or "").strip() or None,
        "espn_position": _position(athlete.get("position")) or None,
    }


class CachedESPNReference:
    """Finite file cache with bounded requests and explicit provider backoff."""

    def __init__(self, client: ESPNClient, cache_dir: Path, *, delay_seconds: float) -> None:
        self.client = client
        self.cache_dir = cache_dir
        self.delay_seconds = max(0.2, delay_seconds)
        self.rate_limit_events = 0
        self.cache_hits = 0
        self.new_requests = 0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, category: str, key: str) -> Path:
        safe_key = re.sub(r"[^A-Za-z0-9._-]+", "-", key)
        return self.cache_dir / category / f"{safe_key}.json"

    def _metadata_path(self, category: str, key: str) -> Path:
        return self._path(category, key).with_suffix(".meta.json")

    def _rate_limit_path(self) -> Path:
        return self.cache_dir / "rate-limit.json"

    def _assert_not_rate_limited(self) -> None:
        path = self._rate_limit_path()
        if not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            resume_at = datetime.fromisoformat(str(payload.get("resume_at", "")).replace("Z", "+00:00"))
        except (ValueError, json.JSONDecodeError):
            return
        if resume_at.tzinfo is None:
            resume_at = resume_at.replace(tzinfo=timezone.utc)
        if resume_at > datetime.now(timezone.utc):
            raise RateLimitPaused(resume_at.astimezone(timezone.utc))

    def _record_rate_limit(self, retry_after: str | None) -> None:
        try:
            delay = max(self.delay_seconds, float(retry_after or 60))
        except ValueError:
            delay = max(self.delay_seconds, 60)
        resume_at = datetime.now(timezone.utc).timestamp() + delay
        payload = {
            "event": "http_429",
            "captured_at": _utc_now(),
            "retry_after_seconds": delay,
            "resume_at": datetime.fromtimestamp(resume_at, timezone.utc).isoformat(),
        }
        temporary_path = self._rate_limit_path().with_suffix(".tmp")
        temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary_path.replace(self._rate_limit_path())
        self.rate_limit_events += 1
        raise RateLimitPaused(datetime.fromtimestamp(resume_at, timezone.utc))

    def _write_metadata(self, category: str, key: str, payload: dict[str, Any], *, cached: bool) -> None:
        path = self._metadata_path(category, key)
        if path.is_file():
            return
        source_path = self._path(category, key)
        captured_at = datetime.fromtimestamp(source_path.stat().st_mtime, timezone.utc).isoformat() if cached else _utc_now()
        metadata = {
            "endpoint_feed": category,
            "reference_id": key,
            "captured_at": captured_at,
            "http_status": 200,
            "payload_sha256": _hash(payload),
            "parser_version": PARSER_VERSION,
        }
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary_path.replace(path)

    def _load_or_fetch(self, category: str, key: str, fetch: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        path = self._path(category, key)
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.cache_hits += 1
                self._write_metadata(category, key, payload, cached=True)
                return payload
            except json.JSONDecodeError:
                # A killed dry run can leave a partial cache entry. Treat it
                # as absent and fetch it again; never use malformed evidence.
                pass
        self._assert_not_rate_limited()
        try:
            payload = fetch()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 403:
                raise RuntimeError("ESPN returned 403; importer stopped without any bypass.") from error
            if error.response.status_code == 429:
                self._record_rate_limit(error.response.headers.get("Retry-After"))
            else:
                raise
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary_path.replace(path)
        self.new_requests += 1
        self._write_metadata(category, key, payload, cached=False)
        time.sleep(self.delay_seconds)
        return payload

    def scoreboard(self, season: int, week: int) -> list[dict[str, Any]]:
        payload = self._load_or_fetch(
            "scoreboards", f"{season}-week-{week}",
            lambda: {"events": self.client.get_scoreboard_events(season=season, week=week)},
        )
        events = payload.get("events") if isinstance(payload, dict) else []
        return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []

    def roster(self, team_id: str) -> dict[str, Any]:
        return self._load_or_fetch("rosters", team_id, lambda: self.client.get_team_roster(team_id))

    def profile(self, player_id: str) -> dict[str, Any]:
        try:
            return self._load_or_fetch("profiles", player_id, lambda: self.client.get_athlete_profile(player_id))
        except httpx.HTTPStatusError as error:
            # A missing/stale profile cannot establish identity. It is a
            # review row, not a reason to discard every other safe mapping.
            # 403 and rate limiting remain hard stops handled above.
            if error.response.status_code in {403, 429}:
                raise
            return {"_reference_error": f"HTTP {error.response.status_code}"}
        except httpx.TimeoutException:
            return {"_reference_error": "timeout"}


def _event_facts(event: dict[str, Any], *, season: int, requested_week: int) -> dict[str, Any] | None:
    event_id = str(event.get("id") or "").strip()
    competitions = event.get("competitions") if isinstance(event.get("competitions"), list) else []
    competition = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    competitors = competition.get("competitors") if isinstance(competition.get("competitors"), list) else []
    by_home_away: dict[str, dict[str, Any]] = {}
    for entry in competitors:
        if not isinstance(entry, dict):
            continue
        team = entry.get("team") if isinstance(entry.get("team"), dict) else {}
        side = str(entry.get("homeAway") or "").lower()
        if side in {"home", "away"}:
            by_home_away[side] = team
    home, away = by_home_away.get("home"), by_home_away.get("away")
    if not event_id.isdigit() or not home or not away:
        return None
    home_name = str(home.get("location") or home.get("shortDisplayName") or "").strip()
    away_name = str(away.get("location") or away.get("shortDisplayName") or "").strip()
    kickoff = str(event.get("date") or competition.get("date") or "").strip()
    if not home_name or not away_name or not kickoff:
        return None
    try:
        kickoff_at = datetime.fromisoformat(kickoff.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
    return {
        "espn_event_id": event_id,
        "season": season,
        "week": int((event.get("week") or {}).get("number") or requested_week),
        "home_team": home_name,
        "away_team": away_name,
        "home_team_id": str(home.get("id") or "").strip() or None,
        "away_team_id": str(away.get("id") or "").strip() or None,
        "kickoff": kickoff_at.isoformat(),
        "status": str(((event.get("status") or {}).get("type") or {}).get("state") or "scheduled").lower(),
    }


def plan_schedule(events: list[dict[str, Any]], *, season: int, weeks: list[int], internal_schools: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    planned: dict[str, dict[str, Any]] = {}
    review: list[dict[str, Any]] = []
    for week, event in zip(weeks, events, strict=True):
        facts = _event_facts(event, season=season, requested_week=week)
        if facts is None:
            continue
        home_key, away_key = _school_key(facts["home_team"]), _school_key(facts["away_team"])
        if home_key not in internal_schools and away_key not in internal_schools:
            continue
        previous = planned.get(facts["espn_event_id"])
        if previous and previous != facts:
            review.append({"reason": "duplicate_espn_event_conflict", "event": facts})
            continue
        planned[facts["espn_event_id"]] = facts
    return list(planned.values()), review


def plan_player_identities(
    players: list[Player],
    roster_rows: list[dict[str, Any]],
    profile_lookup: Callable[[str], dict[str, Any]],
    existing: dict[int, PlayerProviderId],
) -> list[dict[str, Any]]:
    by_school_name_position: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in roster_rows:
        by_school_name_position[(_school_key(row["espn_team"]), normalize_exact_name(row["espn_display_name"]), row["espn_position"])].append(row)
    records: list[dict[str, Any]] = []
    for player in players:
        key = (_school_key(player.school), normalize_exact_name(player.name), _position(player.position))
        candidates = by_school_name_position.get(key, [])
        base = {
            "internal_player_id": player.id,
            "player_name": player.name,
            "school": player.school,
            "position": player.position,
            "depth_chart_slot": player.depth_chart_position,
            "review_priority": _review_priority(player),
            "verification_method": "exact_roster_name_school_position_plus_profile",
            "verified_at": _utc_now(),
            "parser_version": PARSER_VERSION,
        }
        if len(candidates) != 1:
            records.append({**base, "status": "unresolved" if not candidates else "needs_review", "reason": "missing_exact_roster_candidate" if not candidates else "multiple_exact_roster_candidates"})
            continue
        candidate = candidates[0]
        profile_payload = profile_lookup(candidate["espn_player_id"])
        if profile_payload.get("_reference_error"):
            records.append(
                {
                    **base,
                    **candidate,
                    "status": "needs_review",
                    "reason": "profile_reference_unavailable",
                    "reference_error": profile_payload["_reference_error"],
                }
            )
            continue
        profile = profile_facts(profile_payload)
        profile_matches = (
            profile["espn_player_id"] == candidate["espn_player_id"]
            and normalize_exact_name(profile["espn_display_name"]) == normalize_exact_name(player.name)
            and _school_key(profile["espn_team"]) == _school_key(player.school)
            and profile["espn_position"] == _position(player.position)
        )
        if not profile_matches:
            records.append({**base, **candidate, **profile, "status": "needs_review", "reason": "profile_name_school_or_position_mismatch"})
            continue
        prior = existing.get(player.id)
        if prior and (prior.provider_player_id != candidate["espn_player_id"] or prior.verification_status == "verified"):
            if prior.provider_player_id != candidate["espn_player_id"]:
                records.append({**base, **candidate, **profile, "status": "needs_review", "reason": "existing_provider_mapping_conflict"})
                continue
        records.append(
            {
                **base,
                **candidate,
                **profile,
                "status": "verified",
                "reason": None,
                "evidence_source": "ESPN team roster and athlete profile",
                "source_snapshot_hash": _hash(profile_payload),
            }
        )
    ids = Counter(record.get("espn_player_id") for record in records if record.get("status") == "verified")
    for record in records:
        if record.get("status") == "verified" and ids[record["espn_player_id"]] > 1:
            record["status"] = "needs_review"
            record["reason"] = "duplicate_espn_player_id_candidate"
    return records


def _summary(records: list[dict[str, Any]]) -> dict[str, int | float]:
    counts = Counter(record["status"] for record in records)
    total = len(records)
    return {"total": total, "auto_verified": counts["verified"], "needs_review": counts["needs_review"], "unresolved": counts["unresolved"], "verified_percent": round(100 * counts["verified"] / total, 2) if total else 0.0}


def _player_summary(records: list[dict[str, Any]]) -> dict[str, int | float]:
    summary = _summary(records)
    summary["duplicate_espn_ids"] = len({record.get("espn_player_id") for record in records if record.get("reason") == "duplicate_espn_player_id_candidate"})
    summary["conflicts"] = sum(1 for record in records if "conflict" in str(record.get("reason") or ""))
    summary["invalid_espn_ids"] = sum(1 for record in records if record.get("espn_player_id") and not str(record["espn_player_id"]).isdigit())
    for priority in ("P0", "P1", "P2"):
        summary[f"{priority.lower()}_review"] = sum(1 for record in records if record.get("status") != "verified" and record.get("review_priority") == priority)
    return summary


def _game_summary(records: list[dict[str, Any]], review: list[dict[str, Any]]) -> dict[str, int | float]:
    total = len(records) + len(review)
    return {
        "total_relevant_games": total,
        "verified_event_ids": len(records),
        "unresolved_events": len(review),
        "conflicting_events": sum(1 for row in review if "conflict" in str(row.get("reason") or "")),
        "duplicate_events": sum(1 for row in review if "duplicate" in str(row.get("reason") or "")),
        "tbd_kickoffs": sum(1 for row in review if "kickoff" in str(row.get("reason") or "")),
        "verified_percent": round(100 * len(records) / total, 2) if total else 0.0,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, title: str, summary: dict[str, Any], note: str) -> None:
    lines = [f"# {title}", ""]
    lines.extend(f"- {key.replace('_', ' ').title()}: {value}" for key, value in summary.items())
    lines.extend(["", note, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def apply_verified_player_mappings(db: Session, records: list[dict[str, Any]]) -> int:
    applied = 0
    for record in records:
        if record["status"] != "verified":
            continue
        try:
            upsert_player_provider_mapping(
                db,
                player_id=record["internal_player_id"],
                provider="espn",
                provider_player_id=record["espn_player_id"],
                provider_team_id=record.get("espn_team_id"),
                match_confidence=1.0,
                verification_status="verified",
                reason="Exact ESPN current roster and athlete-profile identity match.",
            )
        except ProviderIdentityConflict:
            raise RuntimeError(f"refusing to apply conflicting mapping for player {record['internal_player_id']}") from None
        applied += 1
    return applied


def apply_verified_schedule(db: Session, records: list[dict[str, Any]]) -> int:
    applied = 0
    for record in records:
        kickoff = datetime.fromisoformat(record["kickoff"])
        existing = db.query(Game).filter_by(external_id=record["espn_event_id"]).one_or_none()
        if existing is None:
            existing = Game(
                external_id=record["espn_event_id"], season=record["season"], week=record["week"],
                home_team=record["home_team"], away_team=record["away_team"], start_date=kickoff,
                schedule_status=record["status"],
            )
            db.add(existing)
            db.flush()
        elif (
            {existing.home_team, existing.away_team} != {record["home_team"], record["away_team"]}
            or existing.start_date is None
            or _as_utc(existing.start_date) != _as_utc(kickoff)
        ):
            raise RuntimeError(f"refusing conflicting existing ESPN event {record['espn_event_id']}")
        for team_name, opponent_name, location in ((record["home_team"], record["away_team"], "home"), (record["away_team"], record["home_team"], "away")):
            canonical = canonical_school_name(team_name)
            if not canonical:
                continue
            row = db.query(TeamSchedule).filter_by(team_name=canonical, season=record["season"], week=record["week"]).one_or_none()
            if row and row.game_id not in {None, existing.id}:
                raise RuntimeError(f"refusing conflicting schedule for {canonical} week {record['week']}")
            if row is None:
                row = TeamSchedule(team_name=canonical, season=record["season"], week=record["week"], location=location)
                db.add(row)
            row.game_id, row.opponent_name, row.kickoff_at, row.game_date = existing.id, opponent_name, kickoff, kickoff.date()
            row.is_bye, row.date_confirmed, row.source_url = False, True, "https://site.api.espn.com/"
        applied += 1
    return applied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or apply strict ESPN player and game identities.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, action="append", dest="weeks")
    parser.add_argument("--cache-dir", type=Path, default=Path("reports/.cache/espn-identity-import"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    parser.add_argument("--request-delay-seconds", type=float, default=1.0)
    parser.add_argument("--apply", action="store_true", help="Persist only verified, unambiguous mappings to the current database.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_models_registered()
    weeks = args.weeks or list(range(1, 18))
    with SessionLocal() as db, ESPNClient() as client:
        players = db.query(Player).filter(canonical_fantasy_player_filter(args.season)).order_by(Player.id).all()
        existing = {row.player_id: row for row in db.query(PlayerProviderId).filter_by(provider="espn").all()}
        schools = {_school_key(player.school) for player in players}
        reference = CachedESPNReference(client, args.cache_dir / str(args.season), delay_seconds=args.request_delay_seconds)
        try:
            scoreboards = [(week, event) for week in weeks for event in reference.scoreboard(args.season, week)]
            schedule_records, schedule_review = plan_schedule([event for _, event in scoreboards], season=args.season, weeks=[week for week, _ in scoreboards], internal_schools=schools)
            team_ids = {
                team_id
                for record in schedule_records
                for team_name, team_id in (
                    (record.get("home_team"), record.get("home_team_id")),
                    (record.get("away_team"), record.get("away_team_id")),
                )
                if team_id and _school_key(team_name) in schools
            }
            roster_rows = [athlete for team_id in sorted(team_ids) for athlete in flatten_roster(reference.roster(team_id))]
            player_records = plan_player_identities(players, roster_rows, reference.profile, existing)
        except RateLimitPaused as error:
            db.rollback()
            print(json.dumps({
                "state": "rate_limited",
                "resume_at": error.resume_at.isoformat(),
                "cache_hits": reference.cache_hits,
                "new_requests": reference.new_requests,
                "rate_limit_events": reference.rate_limit_events,
            }, sort_keys=True))
            return 75
        player_payload = {"season": args.season, "generated_at": _utc_now(), "mode": "apply" if args.apply else "dry_run", "summary": _player_summary(player_records), "records": player_records}
        game_summary = _game_summary(schedule_records, schedule_review)
        game_payload = {"season": args.season, "generated_at": _utc_now(), "mode": "apply" if args.apply else "dry_run", "summary": game_summary, "records": schedule_records, "review": schedule_review}
        _write_report(args.report_dir / f"espn-player-readiness-{args.season}.json", player_payload)
        _write_report(args.report_dir / f"espn-game-readiness-{args.season}.json", game_payload)
        _write_markdown(args.report_dir / f"espn-player-readiness-{args.season}.md", "ESPN player readiness", player_payload["summary"], "Only exact roster/profile matches are marked verified.")
        _write_markdown(args.report_dir / f"espn-game-readiness-{args.season}.md", "ESPN game readiness", game_payload["summary"], "Numeric event IDs are accepted only with both event participants and an explicit kickoff.")
        if args.apply:
            applied_players = apply_verified_player_mappings(db, player_records)
            applied_games = apply_verified_schedule(db, schedule_records)
            db.commit()
            print(json.dumps({"applied_players": applied_players, "applied_games": applied_games, "players": player_payload["summary"], "games": game_summary, "cache_hits": reference.cache_hits, "new_requests": reference.new_requests, "rate_limit_events": reference.rate_limit_events}, sort_keys=True))
        else:
            db.rollback()
            print(json.dumps({"players": player_payload["summary"], "games": game_summary, "cache_hits": reference.cache_hits, "new_requests": reference.new_requests, "rate_limit_events": reference.rate_limit_events}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
