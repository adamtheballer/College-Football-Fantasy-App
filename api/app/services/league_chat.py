from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league_message import LeagueMessage


def create_system_message(
    db: Session,
    *,
    league_id: int,
    user_id: int | None,
    body: str,
    message_type: str = "system",
) -> LeagueMessage:
    message = LeagueMessage(
        league_id=league_id,
        user_id=user_id,
        body=body,
        message_type=message_type,
    )
    db.add(message)
    return message
