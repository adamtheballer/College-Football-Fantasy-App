from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.chat import ChatMessage
from collegefootballfantasy_api.app.services.chat_service import create_system_chat_message


def create_system_message(
    db: Session,
    *,
    league_id: int,
    user_id: int | None,
    body: str,
    message_type: str = "system",
) -> ChatMessage:
    """Compatibility wrapper for older system-event callers.

    New code should use ``create_system_chat_message`` with a canonical message type
    and an idempotency event key when the event can be retried.
    """
    mapped_type = "trade_processed" if message_type == "trade" else message_type
    return create_system_chat_message(
        db,
        league_id=league_id,
        body=body,
        message_type=mapped_type,
        metadata_json={"legacy_user_id": user_id} if user_id is not None else {},
    )
