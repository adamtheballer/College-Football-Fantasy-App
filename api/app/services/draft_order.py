from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.schemas.league_flow import (
    DraftOrderEntryRead,
    DraftOrderRead,
    DraftOrderUpdate,
)


def _serialize(draft: Draft, league: League, teams: list[Team]) -> DraftOrderRead:
    positions = [team.draft_position for team in teams]
    return DraftOrderRead(
        draft_order_mode=draft.draft_order_mode or "random",
        max_teams=league.max_teams,
        is_complete=(
            len(teams) == league.max_teams
            and set(positions) == set(range(1, league.max_teams + 1))
        ),
        entries=[
            DraftOrderEntryRead(
                team_id=team.id,
                team_name=team.name,
                owner_user_id=team.owner_user_id,
                owner_name=team.owner_name,
                draft_position=team.draft_position,
            )
            for team in sorted(teams, key=lambda team: (team.draft_position is None, team.draft_position or 0, team.id))
        ],
    )


def update_draft_order(db: Session, *, league: League, payload: DraftOrderUpdate) -> DraftOrderRead:
    """Persist a partial commissioner order before a scheduled draft begins.

    Empty slots are allowed so a commissioner can build an order while people
    join. The start path, not this editor, enforces a full finalized order.
    """
    try:
        draft = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().one_or_none()
        if draft is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
        if draft.status != "scheduled" or league.status not in {"pre_draft", "scheduled"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft order can only be changed before the draft starts")

        teams = db.query(Team).filter(Team.league_id == league.id).with_for_update().all()
        team_ids = {team.id for team in teams}
        requested_team_ids = [entry.team_id for entry in payload.entries]
        requested_positions = [entry.draft_position for entry in payload.entries]
        if len(set(requested_team_ids)) != len(requested_team_ids):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="a team can appear only once in the draft order")
        if len(set(requested_positions)) != len(requested_positions):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="draft positions must be unique")
        if any(team_id not in team_ids for team_id in requested_team_ids):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="draft order contains a team that is not in this league")
        if any(position > league.max_teams for position in requested_positions):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="draft position exceeds league size")

        draft.draft_order_mode = payload.draft_order_mode
        # Random order has no preview order: it is deliberately generated only
        # once, atomically, when the full draft starts.
        for team in teams:
            team.draft_position = None
        if payload.draft_order_mode == "custom":
            position_by_team = {entry.team_id: entry.draft_position for entry in payload.entries}
            for team in teams:
                team.draft_position = position_by_team.get(team.id)
        db.commit()
        return _serialize(draft, league, teams)
    except Exception:
        db.rollback()
        raise
