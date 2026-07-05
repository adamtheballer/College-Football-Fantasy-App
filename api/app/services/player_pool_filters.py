from sqlalchemy import and_, func, or_

from collegefootballfantasy_api.app.models.player import Player


def generated_test_player_filter():
    name = func.lower(func.trim(Player.name))
    school = func.lower(func.trim(Player.school))
    return ~or_(
        and_(name.like("smoke player %"), school.like("smoke school %")),
        and_(name.like("smoke raw player %"), school.like("smoke raw school %")),
    )
