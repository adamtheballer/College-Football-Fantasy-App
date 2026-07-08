from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class ProviderPayloadValidationError(ValueError):
    pass


def _has_any(row: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(row.get(key) not in (None, "") for key in keys)


def _has_stat_value(row: dict[str, Any]) -> bool:
    metadata_keys = {
        "PlayerID",
        "PlayerId",
        "player_id",
        "playerId",
        "ExternalID",
        "external_id",
        "ESPNPlayerID",
        "PlayerName",
        "Name",
        "name",
        "player_name",
        "School",
        "Team",
        "team",
        "TeamName",
        "team_name",
        "TeamAliases",
        "GameKey",
        "GameId",
        "EventId",
        "event_id",
        "game_id",
    }
    for key, value in row.items():
        if key in metadata_keys:
            continue
        if value not in (None, "", "--"):
            return True
    return False


class _ProviderPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    @classmethod
    def validate_row(cls, row: dict[str, Any]) -> dict[str, Any]:
        try:
            return cls.model_validate(row).model_dump(mode="json", by_alias=True)
        except Exception as exc:
            raise ProviderPayloadValidationError(str(exc)) from exc


class SportsDataPlayerGameStatPayload(_ProviderPayload):
    @model_validator(mode="after")
    def validate_payload(self) -> "SportsDataPlayerGameStatPayload":
        row = dict(self.__pydantic_extra__ or {})
        if not _has_any(row, ("PlayerID", "PlayerId", "player_id", "playerId", "ExternalID", "external_id")):
            raise ValueError("missing provider player id")
        if not _has_stat_value(row):
            raise ValueError("missing stat values")
        return self


class ESPNPlayerStatPayload(_ProviderPayload):
    @model_validator(mode="after")
    def validate_payload(self) -> "ESPNPlayerStatPayload":
        row = dict(self.__pydantic_extra__ or {})
        if not _has_any(row, ("ESPNPlayerID", "PlayerName")):
            raise ValueError("missing ESPN player identity")
        if not _has_stat_value(row):
            raise ValueError("missing stat values")
        return self


class RotowireInjuryPayload(_ProviderPayload):
    @model_validator(mode="after")
    def validate_payload(self) -> "RotowireInjuryPayload":
        row = dict(self.__pydantic_extra__ or {})
        if not _has_any(row, ("PlayerName", "Name", "name", "player_name")):
            raise ValueError("missing player name")
        if not _has_any(row, ("Status", "status", "InjuryStatus", "injury_status")):
            raise ValueError("missing injury status")
        return self
