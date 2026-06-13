from sqlalchemy import and_, func, or_

from api.app.models.player import Player


def generated_test_player_filter():
    name = func.lower(func.trim(Player.name))
    school = func.lower(func.trim(Player.school))
    return ~or_(
        and_(name.like("smoke player %"), school.like("smoke school %")),
        and_(name.like("smoke raw player %"), school.like("smoke raw school %")),
    )


def is_generated_test_player(player: Player) -> bool:
    name = (player.name or "").strip().lower()
    school = (player.school or "").strip().lower()
    return (
        name.startswith("smoke player ")
        and school.startswith("smoke school ")
    ) or (
        name.startswith("smoke raw player ")
        and school.startswith("smoke raw school ")
    )
