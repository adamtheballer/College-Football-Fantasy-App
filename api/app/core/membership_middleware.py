from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from collegefootballfantasy_api.app.api.deps import get_optional_current_user
from collegefootballfantasy_api.app.core.player_picture_access import (
    picture_permission,
    membership_mutation_actor,
)
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.services.membership import (
    picture_access,
    rollout_active,
)


async def membership_picture_context(request, call_next):
    # No additional query or behavior change before the explicit 2027 launch.
    if not rollout_active():
        return await call_next(request)

    def permission():
        factory = request.app.dependency_overrides.get(get_db, get_db)
        generator = factory()
        db = next(generator)
        try:
            try:
                user = get_optional_current_user(
                    db, request.headers.get("authorization")
                )
            except HTTPException:
                user = None  # Protected endpoints still reject invalid auth normally.
            return picture_access(db, user), user.id if user else None
        finally:
            generator.close()

    allowed, user_id = await run_in_threadpool(permission)
    token = picture_permission.set(allowed)
    # Guard manual league actions through the existing shared authorization helpers.
    # Background lineup/waiver/draft processing has no request actor and keeps running.
    actor = membership_mutation_actor.set(
        user_id if request.method in {"POST", "PUT", "PATCH", "DELETE"} else None
    )
    try:
        response = await call_next(request)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = ", ".join(
            filter(None, [response.headers.get("Vary"), "Authorization"])
        )
        return response
    finally:
        picture_permission.reset(token)
        membership_mutation_actor.reset(actor)
