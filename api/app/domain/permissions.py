from __future__ import annotations

from dataclasses import dataclass


class PermissionAction:
    ADMIN_ACCESS = "admin.access"
    CREATE_LEAGUE = "league.create"
    READ_LEAGUE = "league.read"
    UPDATE_LEAGUE = "league.update"
    INVITE_MEMBER = "league.invite_member"
    REMOVE_MEMBER = "league.remove_member"
    DRAFT_PICK = "draft.pick"
    ROSTER_MOVE = "roster.move"
    LINEUP_CHANGE = "lineup.change"
    TRADE_PROPOSE = "trade.propose"
    TRADE_ACCEPT = "trade.accept"
    WAIVER_CLAIM = "waiver.claim"
    SCORE_RECALC = "score.recalculate"
    COMMISSIONER_OVERRIDE = "commissioner.override"


class PermissionRole:
    ANONYMOUS = "anonymous"
    UNVERIFIED_USER = "unverified_user"
    VERIFIED_USER = "verified_user"
    LEAGUE_MEMBER = "league_member"
    TEAM_OWNER = "team_owner"
    COMMISSIONER = "commissioner"
    ADMIN = "admin"


COMMISSIONER_ACTIONS = {
    PermissionAction.UPDATE_LEAGUE,
    PermissionAction.INVITE_MEMBER,
    PermissionAction.REMOVE_MEMBER,
    PermissionAction.SCORE_RECALC,
    PermissionAction.COMMISSIONER_OVERRIDE,
}

MEMBER_ACTIONS = {
    PermissionAction.READ_LEAGUE,
    PermissionAction.TRADE_PROPOSE,
    PermissionAction.WAIVER_CLAIM,
}

TEAM_OWNER_ACTIONS = {
    PermissionAction.DRAFT_PICK,
    PermissionAction.ROSTER_MOVE,
    PermissionAction.LINEUP_CHANGE,
    PermissionAction.TRADE_ACCEPT,
}


@dataclass(frozen=True)
class PermissionContext:
    authenticated: bool
    verified: bool
    admin: bool = False
    league_member: bool = False
    commissioner: bool = False
    team_owner: bool = False

    @property
    def role(self) -> str:
        if self.admin:
            return PermissionRole.ADMIN
        if self.commissioner:
            return PermissionRole.COMMISSIONER
        if self.team_owner:
            return PermissionRole.TEAM_OWNER
        if self.league_member:
            return PermissionRole.LEAGUE_MEMBER
        if self.verified:
            return PermissionRole.VERIFIED_USER
        if self.authenticated:
            return PermissionRole.UNVERIFIED_USER
        return PermissionRole.ANONYMOUS


def can(context: PermissionContext, action: str) -> bool:
    if context.admin:
        return True

    if action == PermissionAction.CREATE_LEAGUE:
        return context.verified

    if not context.authenticated:
        return False

    if action in COMMISSIONER_ACTIONS:
        return context.commissioner

    if action in TEAM_OWNER_ACTIONS:
        return context.team_owner or context.commissioner

    if action in MEMBER_ACTIONS:
        return context.league_member or context.team_owner or context.commissioner

    if action == PermissionAction.ADMIN_ACCESS:
        return context.admin

    return False
