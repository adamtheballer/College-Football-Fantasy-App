from collections import defaultdict

from sqlalchemy.orm import Session

from api.app.models.mock_draft_participant import MockDraftParticipant
from api.app.models.mock_draft_pick import MockDraftPick
from api.app.models.mock_draft_session import MockDraftSession
from api.app.models.player import Player
from api.app.schemas.mock_draft import (
    MockDraftHistoryRead,
    MockDraftParticipantRead,
    MockDraftPickRead,
    MockDraftRosterRead,
)


def _participant_to_read(row: MockDraftParticipant) -> MockDraftParticipantRead:
    return MockDraftParticipantRead(
        id=row.id,
        mock_draft_id=row.mock_draft_id,
        user_id=row.user_id,
        display_name=row.display_name,
        team_name=row.team_name,
        participant_type=row.participant_type,  # type: ignore[arg-type]
        seat_number=row.seat_number,
        draft_position=row.draft_position,
        is_host=bool(row.is_host),
        is_ready=bool(row.is_ready),
        joined_at=row.joined_at,
        left_at=row.left_at,
        last_seen_at=row.last_seen_at,
        connection_status=row.connection_status,
        auto_pick_count=int(row.auto_pick_count or 0),
    )


def build_mock_draft_history(db: Session, session_row: MockDraftSession) -> MockDraftHistoryRead:
    participants = (
        db.query(MockDraftParticipant)
        .filter(MockDraftParticipant.mock_draft_id == session_row.id)
        .order_by(MockDraftParticipant.draft_position.asc().nullslast(), MockDraftParticipant.seat_number.asc())
        .all()
    )
    participant_reads = [_participant_to_read(row) for row in participants]
    participant_by_id = {row.id: row for row in participants}
    pick_rows = (
        db.query(MockDraftPick, Player)
        .join(Player, Player.id == MockDraftPick.player_id)
        .filter((MockDraftPick.mock_draft_id == session_row.id) | (MockDraftPick.session_id == session_row.id))
        .order_by(MockDraftPick.overall_pick.asc())
        .all()
    )

    picks: list[MockDraftPickRead] = []
    by_round: dict[int, list[MockDraftPickRead]] = defaultdict(list)
    by_participant: dict[int, list[MockDraftPickRead]] = defaultdict(list)
    for pick, player in pick_rows:
        participant = participant_by_id.get(pick.participant_id or 0)
        if participant is None:
            continue
        read = MockDraftPickRead(
            id=pick.id,
            mock_draft_id=pick.mock_draft_id or pick.session_id,
            participant_id=participant.id,
            participant_name=participant.display_name,
            team_name=participant.team_name,
            player_id=player.id,
            player_name=player.name,
            player_position=player.position,
            player_school=player.school,
            overall_pick=pick.overall_pick,
            round_number=pick.round_number,
            round_pick=pick.round_pick,
            pick_source=pick.pick_source,  # type: ignore[arg-type]
            auto_pick_reason=pick.auto_pick_reason,
            made_by_user_id=pick.made_by_user_id,
            created_at=pick.created_at,
        )
        picks.append(read)
        by_round[pick.round_number].append(read)
        by_participant[participant.id].append(read)

    rosters = [
        MockDraftRosterRead(
            participant_id=participant.id,
            participant_name=participant.display_name,
            team_name=participant.team_name,
            picks=by_participant.get(participant.id, []),
        )
        for participant in participants
    ]
    picks_by_round = [
        {
            "round": round_number,
            "picks": [pick.model_dump(mode="json") for pick in round_picks],
        }
        for round_number, round_picks in sorted(by_round.items())
    ]
    lines = [
        f"{session_row.name} Draft History",
        f"Status: {session_row.status}",
        "",
        "Draft Order:",
        *[
            f"{participant.draft_position or participant.seat_number}. {participant.team_name} ({participant.display_name})"
            for participant in participants
        ],
        "",
        "Picks:",
        *[
            f"{pick.round_number}.{pick.round_pick} {pick.team_name}: {pick.player_name} ({pick.player_position}, {pick.player_school})"
            for pick in picks
        ],
    ]
    plain_text = "\n".join(lines)
    html = (
        f"<h1>{session_row.name} Draft History</h1>"
        "<h2>Draft Order</h2><ol>"
        + "".join(f"<li>{participant.team_name} ({participant.display_name})</li>" for participant in participants)
        + "</ol><h2>Picks</h2><ol>"
        + "".join(
            f"<li>{pick.round_number}.{pick.round_pick} {pick.team_name}: "
            f"{pick.player_name} ({pick.player_position}, {pick.player_school})</li>"
            for pick in picks
        )
        + "</ol>"
    )
    return MockDraftHistoryRead(
        mock_draft_id=session_row.id,
        draft_name=session_row.name,
        completed_at=session_row.completed_at,
        participants=participant_reads,
        draft_order=participant_reads,
        picks=picks,
        picks_by_round=picks_by_round,
        rosters=rosters,
        plain_text=plain_text,
        html=html,
        pick_count=len(picks),
    )
