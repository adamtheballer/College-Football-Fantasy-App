"""Permanent self-service account deletion with personal-data scrubbing.

Deleting the user record lets database cascades remove private account data
(sessions, credentials, mock drafts, preferences, watchlists, and entries).
Some league history intentionally survives for other managers, so the small
set of retained records is scrubbed before the user is removed.
"""

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.beta_access import BetaAccessCode
from collegefootballfantasy_api.app.models.chat import ChatMessage
from collegefootballfantasy_api.app.models.league_message import LeagueMessage
from collegefootballfantasy_api.app.models.league_rivalry import LeagueRivalry
from collegefootballfantasy_api.app.models.notification import NotificationLog, PushToken
from collegefootballfantasy_api.app.models.saturday_pick import SaturdayPickContest
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User


DELETED_MANAGER_NAME = "Former Manager"
DELETED_MESSAGE_BODY = "This message was deleted with its sender's account."


def permanently_delete_user_account(db: Session, *, user: User) -> None:
    """Remove a user's account and erase their retained personal data.

    This function deliberately does not commit. The caller owns the
    transaction so an API failure cannot leave a half-deleted account.
    """

    user_id = user.id

    # A contest is shared public data. Keep the contest for all entrants but
    # detach its former creator instead of making account deletion impossible.
    db.query(SaturdayPickContest).filter(SaturdayPickContest.created_by_user_id == user_id).update(
        {SaturdayPickContest.created_by_user_id: None},
        synchronize_session=False,
    )

    # Preserve league history for remaining managers, but never keep an
    # identifiable manager or user-selected team name after deletion.
    owned_teams = db.query(Team).filter(Team.owner_user_id == user_id).all()
    for team in owned_teams:
        team.owner_user_id = None
        team.owner_name = DELETED_MANAGER_NAME
        team.name = f"Vacant Team {team.id}"

    # User-authored chat and league-message content is personal data. Retain a
    # neutral placeholder only so threaded history stays understandable.
    db.query(ChatMessage).filter(ChatMessage.sender_user_id == user_id).update(
        {
            ChatMessage.sender_user_id: None,
            ChatMessage.body: DELETED_MESSAGE_BODY,
            ChatMessage.metadata_json: {},
            ChatMessage.client_message_id: None,
        },
        synchronize_session=False,
    )
    db.query(LeagueMessage).filter(LeagueMessage.user_id == user_id).update(
        {
            LeagueMessage.user_id: None,
            LeagueMessage.body: DELETED_MESSAGE_BODY,
        },
        synchronize_session=False,
    )

    # Rivalry history can retain both manager and team snapshots, so scrub the
    # departed side before the foreign key becomes NULL.
    for rivalry in db.query(LeagueRivalry).filter(
        (LeagueRivalry.user_a_id == user_id) | (LeagueRivalry.user_b_id == user_id)
    ):
        if rivalry.user_a_id == user_id:
            rivalry.manager_a_name_snapshot = DELETED_MANAGER_NAME
            rivalry.team_a_name_snapshot = "Vacant Team"
        if rivalry.user_b_id == user_id:
            rivalry.manager_b_name_snapshot = DELETED_MANAGER_NAME
            rivalry.team_b_name_snapshot = "Vacant Team"

    # Disable the provider subscription before the user reference disappears;
    # this prevents future mobile push delivery to a deleted account.
    db.query(PushToken).filter(PushToken.user_id == user_id).update(
        {
            PushToken.user_id: None,
            PushToken.user_key: None,
            PushToken.external_user_id: None,
            PushToken.enabled: False,
        },
        synchronize_session=False,
    )
    db.query(NotificationLog).filter(NotificationLog.user_id == user_id).delete(synchronize_session=False)

    # The access-code ledger contains the user's email independent of the FK.
    # Remove redeemed records instead of retaining that email after deletion.
    db.query(BetaAccessCode).filter(BetaAccessCode.redeemed_user_id == user_id).delete(synchronize_session=False)

    db.delete(user)
