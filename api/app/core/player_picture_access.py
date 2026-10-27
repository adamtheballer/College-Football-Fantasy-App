"""Request-scoped portrait permission, including nested Pydantic responses."""

from contextvars import ContextVar
from collegefootballfantasy_api.app.core.config import settings

picture_permission = ContextVar("player_picture_permission", default=None)
membership_mutation_actor = ContextVar("membership_mutation_actor", default=None)


def player_pictures_allowed():
    permission = picture_permission.get()
    if permission is not None:
        return permission
    from collegefootballfantasy_api.app.services.membership import rollout_active

    return False if rollout_active() else settings.player_headshots_enabled
